"""Screen capture via mss + Win32 window utilities (ctypes, no extra dependencies)."""

import ctypes
import ctypes.wintypes
from PIL import Image
import mss


# ---------------------------------------------------------------------------
# Screen capture
# ---------------------------------------------------------------------------

def capture_screen() -> Image.Image | None:
    """Capture the entire virtual desktop (all monitors) as a PIL RGB Image.

    Returns None if capture fails. Uses mss monitors[0] which spans all screens.
    """
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # All monitors combined
            raw = sct.grab(monitor)
            # mss returns BGRA; convert to RGB by dropping alpha and reordering
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return img
    except Exception:
        return None


def get_virtual_screen_offset() -> tuple[int, int]:
    """Return (left, top) of the virtual screen (all monitors) in physical pixels.

    The virtual screen's top-left may be at negative coordinates if a monitor
    is positioned to the left/above the primary monitor.
    """
    with mss.mss() as sct:
        mon = sct.monitors[0]
        return mon["left"], mon["top"]


def is_black_image(img: Image.Image) -> bool:
    """Return True if the image is effectively pure black.

    Detects the known failure mode of capturing exclusive-fullscreen DirectX
    games, where the capture returns a black frame.
    """
    extrema = img.getextrema()
    # Grayscale: extrema is (min, max)
    if isinstance(extrema[0], int):
        return extrema[1] < 5
    # RGB/RGBA: extrema is ((min,max), (min,max), (min,max), ...)
    return all(max_val < 5 for _min, max_val in extrema[:3])


# ---------------------------------------------------------------------------
# Win32 window utilities (ctypes — no pywin32 dependency)
# ---------------------------------------------------------------------------

user32 = ctypes.windll.user32

# Win32 constants
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E

# Callback type for EnumWindows
WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.wintypes.LONG),
        ("top", ctypes.wintypes.LONG),
        ("right", ctypes.wintypes.LONG),
        ("bottom", ctypes.wintypes.LONG),
    ]


def _is_window_visible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisibleW(hwnd))


def _get_window_text(hwnd: int) -> str:
    length = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, buf)
    return buf.value


def _get_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return (x, y, width, height) of a window in screen coords, or None."""
    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    return None


def _find_visible_window(match) -> int | None:
    """Return the first visible top-level window for which match(hwnd) is true."""
    result = []

    def _cb(hwnd, _lparam):
        if match(hwnd):
            result.append(hwnd)
            return False  # Stop enumeration
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return result[0] if result else None


def find_window_by_title(title: str) -> int | None:
    """Find a visible top-level window whose title contains *title*."""
    return _find_visible_window(
        lambda hwnd: _is_window_visible(hwnd) and title in _get_window_text(hwnd)
    )


def find_window_by_class(class_name: str) -> int | None:
    """Find a visible top-level window with the given class name."""
    return _find_visible_window(
        lambda hwnd: _is_window_visible(hwnd) and _get_class_name(hwnd) == class_name
    )


def get_window_info(hwnd: int) -> tuple[str, str, tuple[int, int, int, int]] | None:
    """Return (title, class_name, (x, y, w, h)) for a window, or None."""
    if not user32.IsWindow(hwnd):
        return None
    rect = get_window_rect(hwnd)
    if rect is None:
        return None
    return (_get_window_text(hwnd), _get_class_name(hwnd), rect)


def find_topmost_window_at_point(
    x: int, y: int, exclude_hwnd: int = 0
) -> tuple[int, str, str, tuple[int, int, int, int]] | None:
    """Find the topmost visible top-level window containing screen point (x, y).

    Enumerates windows in Z-order (top to bottom) and returns the first one
    whose rect contains the point, excluding *exclude_hwnd* (the overlay) and
    this app's own Qt windows / system tooltips.

    Returns (hwnd, title, class_name, (x, y, w, h)) or None.
    """
    result = []

    def _cb(hwnd, _lparam):
        if hwnd == exclude_hwnd or not _is_window_visible(hwnd):
            return True
        rect = get_window_rect(hwnd)
        if rect is None:
            return True
        rx, ry, rw, rh = rect
        if rw <= 1 or rh <= 1:
            return True  # Skip minimized/tiny windows
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            cls = _get_class_name(hwnd)
            if "Qt" in cls or cls == "tooltips_class32":
                return True  # Our own overlay UI / tooltips
            result.append((hwnd, _get_window_text(hwnd), cls, rect))
            return False  # Found the topmost — stop
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return result[0] if result else None
