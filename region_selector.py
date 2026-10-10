"""Fullscreen overlay for region/window selection.

Shows a darkened screenshot and lets the user drag a rectangle or click a window.
Emits region_selected (physical-pixel coords) or cancelled.
"""

import io
from PIL import Image
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QGuiApplication
from PySide6.QtWidgets import QWidget

from screen_capture import find_topmost_window_at_point, get_virtual_screen_offset


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    """Convert a PIL Image to QPixmap via PNG encoding (safe, no lifetime issues)."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue())
    return pixmap


class RegionSelector(QWidget):
    """Fullscreen overlay for selecting a screen region.

    User drags to select a rectangle (region mode) or clicks to select a window
    (window mode). Emits region_selected(x1,y1,x2,y2) in physical pixels
    or window_selected(hwnd) or cancelled.
    """

    region_selected = Signal(int, int, int, int)  # physical-pixel coords
    window_selected = Signal(int)                   # hwnd
    cancelled = Signal()

    # Minimum drag distance to distinguish a drag from a click (logical pixels)
    CLICK_THRESHOLD = 5

    def __init__(self, screenshot: Image.Image, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.pixmap = pil_to_pixmap(screenshot)

        # Window flags: frameless, always-on-top, no taskbar entry
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        # Cover the entire virtual desktop
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)

        # Scale factors: physical pixels per logical pixel
        self.scale_x = screenshot.width / geo.width()
        self.scale_y = screenshot.height / geo.height()

        # Virtual screen offset (physical pixels) — top-left of virtual desktop
        # May be non-zero on multi-monitor setups with monitors to the left/above
        self._offset_x, self._offset_y = get_virtual_screen_offset()

        # Selection state
        self._origin: QPoint | None = None
        self._current_rect: QRect | None = None
        self._hover_rect: QRect | None = None   # Window highlight rect (logical)
        self._hover_hwnd: int | None = None      # Currently hovered window handle
        self._last_hover_pos: QPoint | None = None  # Skip re-queries at same spot

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw screenshot scaled to overlay
        painter.drawPixmap(self.rect(), self.pixmap)

        # Darken everything
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # Redraw selected region at full brightness
        if self._current_rect and self._current_rect.width() > 0:
            self._draw_full_brightness(painter, self._current_rect)
            self._draw_selection_border(painter, self._current_rect)
            self._draw_size_label(painter, self._current_rect)

        # Window hover highlight
        if self._hover_rect and not self._current_rect:
            self._draw_window_highlight(painter, self._hover_rect)

        # Instruction text at top
        self._draw_instructions(painter)

    def _draw_full_brightness(self, painter: QPainter, rect: QRect):
        """Redraw the screenshot portion inside *rect* at full brightness."""
        sx = int(rect.x() * self.scale_x)
        sy = int(rect.y() * self.scale_y)
        sw = max(1, int(rect.width() * self.scale_x))
        sh = max(1, int(rect.height() * self.scale_y))
        source = QRect(sx, sy, sw, sh)
        painter.drawPixmap(rect, self.pixmap, source)

    def _draw_selection_border(self, painter: QPainter, rect: QRect):
        pen = QPen(QColor(0, 174, 255), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    def _draw_size_label(self, painter: QPainter, rect: QRect):
        """Show the physical-pixel dimensions of the current selection."""
        pw = int(rect.width() * self.scale_x)
        ph = int(rect.height() * self.scale_y)
        label = f"{pw} × {ph}"
        font = QFont("Microsoft YaHei", 10)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        # Position below the selection's bottom-right corner
        text_rect = QRect(rect.right() + 6, rect.bottom() + 4, 200, 24)
        # Keep on screen
        if text_rect.right() > self.width():
            text_rect.moveRight(rect.right() - 6)
        if text_rect.bottom() > self.height():
            text_rect.moveBottom(rect.top() - 6)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop, label)

    def _draw_window_highlight(self, painter: QPainter, rect: QRect):
        """Draw a green dashed border around a hovered window."""
        pen = QPen(QColor(0, 255, 100), 3)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 255, 100, 30))
        painter.drawRect(rect)

    def _draw_instructions(self, painter: QPainter):
        font = QFont("Microsoft YaHei", 14, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        text_rect = QRect(0, 30, self.width(), 40)
        painter.drawText(text_rect, Qt.AlignCenter, "拖拽框选区域  |  点击选择窗口  |  ESC 取消")

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._current_rect = QRect(self._origin, self._origin)
            self.update()
        elif event.button() == Qt.RightButton:
            self._do_cancel()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._origin is not None:
            # Dragging — update selection rectangle
            self._current_rect = QRect(self._origin, pos).normalized()
            self.update()
        else:
            # Hovering — highlight the window under the cursor
            self._update_hover(pos)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._origin is None:
            return

        end = event.position().toPoint()
        rect = QRect(self._origin, end).normalized()
        self._origin = None

        # If the drag is tiny, treat as a click → select the window under cursor
        if rect.width() < self.CLICK_THRESHOLD and rect.height() < self.CLICK_THRESHOLD:
            self._current_rect = None
            self.update()
            # Try to select the window at the click position
            if self._hover_hwnd is not None:
                self.window_selected.emit(self._hover_hwnd)
                self.close()
            return

        # Drag selection — convert logical → physical pixels
        x1 = int(rect.x() * self.scale_x)
        y1 = int(rect.y() * self.scale_y)
        x2 = int((rect.x() + rect.width()) * self.scale_x)
        y2 = int((rect.y() + rect.height()) * self.scale_y)

        # Clamp to screenshot bounds
        x1 = max(0, min(x1, self.screenshot.width))
        y1 = max(0, min(y1, self.screenshot.height))
        x2 = max(0, min(x2, self.screenshot.width))
        y2 = max(0, min(y2, self.screenshot.height))

        self.region_selected.emit(x1, y1, x2, y2)
        self.close()

    # ------------------------------------------------------------------
    # Window hover detection
    # ------------------------------------------------------------------

    def _overlay_to_screen(self, local_x: int, local_y: int) -> tuple[int, int]:
        """Convert overlay logical coordinates to physical screen coordinates."""
        phys_x = int(local_x * self.scale_x) + self._offset_x
        phys_y = int(local_y * self.scale_y) + self._offset_y
        return phys_x, phys_y

    def _screen_to_overlay_rect(self, phys_x: int, phys_y: int, phys_w: int, phys_h: int) -> QRect:
        """Convert a physical screen rect to overlay logical coordinates for drawing."""
        local_x = (phys_x - self._offset_x) / self.scale_x
        local_y = (phys_y - self._offset_y) / self.scale_y
        local_w = phys_w / self.scale_x
        local_h = phys_h / self.scale_y
        return QRect(int(local_x), int(local_y), int(local_w), int(local_h))

    def _update_hover(self, pos: QPoint):
        """Find the window under the cursor and update the hover highlight."""
        if pos == self._last_hover_pos:
            return  # Same spot as last query — EnumWindows is not cheap
        self._last_hover_pos = pos

        phys_x, phys_y = self._overlay_to_screen(pos.x(), pos.y())
        try:
            exclude = int(self.winId())
        except Exception:
            exclude = 0

        result = find_topmost_window_at_point(phys_x, phys_y, exclude_hwnd=exclude)
        if result is not None:
            hwnd, title, cls, (rx, ry, rw, rh) = result
            self._hover_hwnd = hwnd
            self._hover_rect = self._screen_to_overlay_rect(rx, ry, rw, rh)
        else:
            self._hover_hwnd = None
            self._hover_rect = None
        self.update()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._do_cancel()

    def _do_cancel(self):
        self.cancelled.emit()
        self.close()

    # ------------------------------------------------------------------
    # Show
    # ------------------------------------------------------------------

    def showEvent(self, _event):
        self.setFocus()
        self.activateWindow()
        self.raise_()
