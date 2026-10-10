"""闪译 (SnapTrans) — main entry point.

Global hotkey → screen capture → region/window selection → vision API translation
→ floating result overlay. System tray resident. Settings dialog with config.json
persistence. Remembers last selection for repeat translation.
"""

import sys

import keyboard
from PIL import Image
from PySide6.QtCore import QObject, Signal, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from config import APP_NAME, load_config, save_config
from screen_capture import (
    capture_screen,
    find_window_by_class,
    find_window_by_title,
    get_virtual_screen_offset,
    get_window_info,
    get_window_rect,
    is_black_image,
)
from region_selector import RegionSelector
from api_client import TranslateWorker, image_to_base64
from result_window import ResultWindow
from tray_icon import TrayIcon
from settings_dialog import SettingsDialog

# Shown when the captured crop is all black (exclusive-fullscreen DirectX games).
BLACK_SCREEN_MSG = "截图失败，请将游戏切换为无边框窗口模式后重试。"


def _clamped_crop(img: Image.Image, x1: int, y1: int, x2: int, y2: int):
    """Crop img to [x1,y1,x2,y2) clamped to bounds; None if the area is empty."""
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img.width, x2), min(img.height, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return img.crop((x1, y1, x2, y2))


class HotkeyBridge(QObject):
    """Bridge between the keyboard library's background thread and Qt's main thread.

    keyboard.add_hotkey fires its callback in keyboard's own thread. We emit a
    Qt signal here, which Qt safely queues to the main thread via auto-connection.
    """

    triggered = Signal()


class TranslationController(QObject):
    """Orchestrates the capture → select → translate → display flow.

    Two selection modes:
      - region: user drags a rectangle (coords stored in config)
      - window: user clicks a window (title+class stored in config)

    On repeat, uses the remembered selection without showing the overlay.
    """

    def __init__(self, tray: TrayIcon):
        super().__init__()
        self.config = load_config()
        self.tray = tray
        self.selector: RegionSelector | None = None
        self.result_window: ResultWindow | None = None
        self.worker: TranslateWorker | None = None
        self.screenshot: Image.Image | None = None

        self.bridge = HotkeyBridge()
        self.bridge.triggered.connect(self.start_translation)
        self._registered_hotkey: str | None = None

    # ------------------------------------------------------------------
    # Hotkey
    # ------------------------------------------------------------------

    def register_hotkey(self, hotkey: str) -> None:
        """(Re)register the global hotkey, replacing the previous one."""
        if self._registered_hotkey:
            try:
                keyboard.remove_hotkey(self._registered_hotkey)
            except (ValueError, KeyError):
                pass  # never got registered
        try:
            keyboard.add_hotkey(hotkey, self.bridge.triggered.emit)
        except Exception as e:
            self.tray.show_message(APP_NAME, f"注册热键失败：{e}\n请检查热键是否被占用。")
            return
        self._registered_hotkey = hotkey

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def start_translation(self, force_reselect: bool = False):
        """Begin capture → select → translate.

        Reuses the remembered selection unless force_reselect is set or the
        remembered selection is invalid.
        """
        if self.selector is not None or (self.worker and self.worker.isRunning()):
            return

        if not self.config.get("api_key"):
            self.tray.show_message(APP_NAME, "未设置 API Key，请先在设置中填写。")
            self.open_settings()
            return

        if force_reselect or not self._reuse_last_selection():
            self._show_selector()

    def reselect(self):
        self.start_translation(force_reselect=True)

    def open_settings(self):
        dialog = SettingsDialog(self.config)
        dialog.config_changed.connect(self._on_config_changed)
        dialog.exec()

    # ------------------------------------------------------------------
    # Selection overlay
    # ------------------------------------------------------------------

    def _show_selector(self):
        screenshot = capture_screen()
        if screenshot is None:
            self.tray.show_message(APP_NAME, "截图失败，请重试。")
            return

        self.screenshot = screenshot
        self.selector = RegionSelector(screenshot)
        self.selector.region_selected.connect(self._on_region_selected)
        self.selector.window_selected.connect(self._on_window_selected)
        self.selector.cancelled.connect(self._on_cancelled)
        self.selector.show()

    def _on_region_selected(self, x1, y1, x2, y2):
        self.selector = None
        screenshot, self.screenshot = self.screenshot, None

        self._remember_region(x1, y1, x2, y2)
        self._translate_region(screenshot, x1, y1, x2, y2)

    def _on_window_selected(self, hwnd: int):
        self.selector = None
        screenshot, self.screenshot = self.screenshot, None

        info = get_window_info(hwnd)
        if info is None:
            self.tray.show_message(APP_NAME, "无法获取窗口信息。")
            return
        title, cls, (rx, ry, rw, rh) = info

        self._remember_window(title, cls)
        self._translate_window_rect(screenshot, rx, ry, rw, rh)

    def _on_cancelled(self):
        self.selector = None
        self.screenshot = None

    def _remember_region(self, x1, y1, x2, y2):
        self.config.update(
            last_mode="region",
            last_region=[x1, y1, x2, y2],
            last_window_title=None,
            last_window_class=None,
        )
        save_config(self.config)

    def _remember_window(self, title, cls):
        self.config.update(
            last_mode="window",
            last_window_title=title,
            last_window_class=cls,
            last_region=None,
        )
        save_config(self.config)

    # ------------------------------------------------------------------
    # Crop → translate (shared by fresh selection and remembered reuse)
    # ------------------------------------------------------------------

    def _translate_region(self, screenshot: Image.Image, x1, y1, x2, y2):
        """Crop a region out of the full screenshot and translate it."""
        crop = _clamped_crop(screenshot, x1, y1, x2, y2)
        if crop is None:
            return
        self._dispatch_crop(crop, self._physical_to_logical_rect(x1, y1, x2, y2))

    def _translate_window_rect(self, screenshot: Image.Image, rx, ry, rw, rh):
        """Crop a window rect (screen coords) out of the full screenshot."""
        offset_x, offset_y = get_virtual_screen_offset()
        sx, sy = max(0, rx - offset_x), max(0, ry - offset_y)
        crop = _clamped_crop(screenshot, sx, sy, sx + rw, sy + rh)
        if crop is None:
            return
        self._dispatch_crop(
            crop, self._physical_to_logical_rect(rx, ry, rx + rw, ry + rh)
        )

    def _dispatch_crop(self, crop: Image.Image, logical_rect: QRect):
        if is_black_image(crop):
            self._show_result(BLACK_SCREEN_MSG, is_error=True)
            return
        self._translate_crop(crop, logical_rect)

    # ------------------------------------------------------------------
    # Remembered selection reuse
    # ------------------------------------------------------------------

    def _reuse_last_selection(self) -> bool:
        """Reuse the last selection. True = flow started (or failed hard);
        False = fall back to the selection overlay."""
        mode = self.config.get("last_mode")

        if mode == "region" and self.config.get("last_region"):
            screenshot = capture_screen()
            if screenshot is None:
                self.tray.show_message(APP_NAME, "截图失败，请重试。")
                return True
            x1, y1, x2, y2 = self.config["last_region"]
            if _clamped_crop(screenshot, x1, y1, x2, y2) is None:
                return False  # degenerate region — show the overlay
            self._translate_region(screenshot, x1, y1, x2, y2)
            return True

        if mode == "window" and (
            self.config.get("last_window_title") or self.config.get("last_window_class")
        ):
            return self._reuse_window()

        return False

    def _reuse_window(self) -> bool:
        """Find the remembered window (class first, then title) and translate."""
        hwnd = None
        if self.config.get("last_window_class"):
            hwnd = find_window_by_class(self.config["last_window_class"])
        if hwnd is None and self.config.get("last_window_title"):
            hwnd = find_window_by_title(self.config["last_window_title"])

        rect = get_window_rect(hwnd) if hwnd else None
        if rect is None or rect[2] <= 1 or rect[3] <= 1:
            return False  # not found or minimized — show the overlay

        screenshot = capture_screen()
        if screenshot is None:
            self.tray.show_message(APP_NAME, "截图失败，请重试。")
            return True
        self._translate_window_rect(screenshot, *rect)
        return True

    # ------------------------------------------------------------------
    # Result windows
    # ------------------------------------------------------------------

    def _new_result_window(self) -> ResultWindow:
        self._close_result()
        window = ResultWindow(
            opacity=self.config.get("opacity", 0.9),
            auto_close=self.config.get("auto_close_seconds", 10),
            auto_close_enabled=self.config.get("auto_close_enabled", True),
        )
        self.result_window = window
        return window

    def _close_result(self):
        if self.result_window:
            self.result_window.close()
            self.result_window = None

    def _show_result(self, text: str, is_error: bool = False):
        """Show a result/error window near the primary screen center."""
        window = self._new_result_window()
        window.show_result(text, is_error=is_error)
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            window.move(
                geo.center().x() - window.width() // 2,
                geo.center().y() - window.height() // 2,
            )
        window.show()

    def _translate_crop(self, crop: Image.Image, logical_rect: QRect):
        """Encode the crop, show a loading window, and start the API worker."""
        window = self._new_result_window()
        window.show_loading("翻译中...")
        window.position_near(logical_rect)
        window.show()

        self.worker = TranslateWorker(image_to_base64(crop), self.config)
        self.worker.success.connect(self._on_translate_success)
        self.worker.error.connect(self._on_translate_error)
        self.worker.start()

    def _on_translate_success(self, text: str):
        if self.result_window:
            self.result_window.show_result(text, is_error=False)
        self.worker = None

    def _on_translate_error(self, error: str):
        if self.result_window:
            self.result_window.show_result(error, is_error=True)
        self.worker = None

    # ------------------------------------------------------------------
    # Config changes
    # ------------------------------------------------------------------

    def _on_config_changed(self):
        old_hotkey = self.config.get("hotkey")
        self.config = load_config()
        new_hotkey = self.config.get("hotkey", "ctrl+alt+q")
        if new_hotkey != old_hotkey:
            self.register_hotkey(new_hotkey)
        self.tray.show_message(APP_NAME, "设置已保存。")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _physical_to_logical_rect(self, x1, y1, x2, y2) -> QRect:
        """Convert physical-pixel screenshot coords to logical screen coords."""
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        return QRect(
            int(x1 / dpr), int(y1 / dpr),
            int((x2 - x1) / dpr), int((y2 - y1) / dpr),
        )

    def cleanup(self):
        if self.selector:
            self.selector.close()
        self._close_result()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)

    tray = TrayIcon()
    tray.show()

    controller = TranslationController(tray)
    tray.translate_triggered.connect(controller.start_translation)
    tray.settings_triggered.connect(controller.open_settings)
    tray.reselect_triggered.connect(controller.reselect)
    tray.quit_triggered.connect(lambda: (controller.cleanup(), tray.hide(), app.quit()))

    hotkey = controller.config.get("hotkey", "ctrl+alt+q")
    controller.register_hotkey(hotkey)

    if not controller.config.get("api_key"):
        tray.show_message(APP_NAME, "首次使用，请先设置 API Key。")
        controller.open_settings()
    tray.show_message(APP_NAME, f"已启动，按 {hotkey} 截图翻译。")

    try:
        ret = app.exec()
    except KeyboardInterrupt:
        ret = 0
    finally:
        keyboard.unhook_all()

    return ret


if __name__ == "__main__":
    sys.exit(main())
