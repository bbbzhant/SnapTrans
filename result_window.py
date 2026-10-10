"""Floating result overlay window — shows translated text on top of everything.

Features:
  - Frameless, always-on-top, semi-transparent
  - Draggable by clicking anywhere
  - Close button (×) top-right
  - Auto-close countdown
  - Error text shown in red
  - Loading state with spinner text
"""

from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout


def _label_style(color: str) -> str:
    return (
        "QLabel {"
        f"  color: {color};"
        "  font-size: 14px;"
        "  font-family: 'Microsoft YaHei', sans-serif;"
        "}"
    )


class ResultWindow(QWidget):
    """A frameless always-on-top window that displays translation results."""

    def __init__(self, opacity: float = 0.9, auto_close: int = 10,
                 auto_close_enabled: bool = True, parent=None):
        super().__init__(parent)
        self._opacity = opacity
        self._auto_close = auto_close
        self._auto_close_enabled = auto_close_enabled

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._drag_pos: QPoint | None = None
        self._countdown = auto_close
        self._is_error = False

        self._build_ui()
        self._setup_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(6)

        # Close button (top-right)
        self.close_btn = QPushButton("×", self)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet(
            "QPushButton {"
            "  border: none;"
            "  color: rgba(255,255,255,180);"
            "  font-size: 16px;"
            "  font-weight: bold;"
            "  background: transparent;"
            "}"
            "QPushButton:hover {"
            "  color: white;"
            "  background: rgba(255,80,80,180);"
            "  border-radius: 12px;"
            "}"
        )
        self.close_btn.clicked.connect(self._manual_close)

        # Close button is positioned absolutely via paintEvent/move
        self.close_btn.move(self.width() - 28, 4)
        self.close_btn.raise_()

        # Result text label
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.label.setText("翻译中...")
        self.label.setStyleSheet(_label_style("white"))
        layout.addWidget(self.label)

        # Countdown label (bottom)
        self.countdown_label = QLabel(self)
        self.countdown_label.setAlignment(Qt.AlignRight)
        self.countdown_label.setStyleSheet(
            "QLabel {"
            "  color: rgba(255,255,255,120);"
            "  font-size: 11px;"
            "}"
        )
        layout.addWidget(self.countdown_label)

        self.setLayout(layout)

    def _setup_timer(self):
        """Start the auto-close countdown timer (only if enabled)."""
        self._update_countdown()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        if self._auto_close_enabled and self._auto_close > 0:
            self._timer.start(1000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_result(self, text: str, is_error: bool = False):
        """Display translation result (or error message in red)."""
        self._is_error = is_error
        self.label.setText(text)
        self.label.setStyleSheet(_label_style("#ff6666" if is_error else "white"))
        self.adjustSize()
        self._position_close_button()

    def show_loading(self, message: str = "翻译中..."):
        """Show a loading state."""
        self._is_error = False
        self.label.setText(message)
        self.label.setStyleSheet(_label_style("rgba(255,255,255,200)"))
        self.adjustSize()
        self._position_close_button()

    def position_near(self, rect: QRect):
        """Position the window below *rect* (the selection area), or above if no space.

        The final position is always clamped to the screen's available area.
        """
        margin = 8
        x = rect.x()
        y = rect.bottom() + margin

        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            if y + self.height() > sg.bottom():
                y = rect.y() - self.height() - margin  # No room below — go above
            x = min(max(x, sg.left() + margin), sg.right() - self.width() - margin)
            y = min(max(y, sg.top() + margin), sg.bottom() - self.height() - margin)

        self.move(x, y)

    # ------------------------------------------------------------------
    # Painting — semi-transparent dark background
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dark semi-transparent rounded rectangle
        bg_color = QColor(20, 20, 30, int(255 * self._opacity))
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_close_button()

    def _position_close_button(self):
        self.close_btn.move(self.width() - 28, 4)
        self.close_btn.raise_()

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Don't start drag if clicking the close button
            if self.close_btn.geometry().contains(event.position().toPoint()):
                return
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ------------------------------------------------------------------
    # Auto-close countdown
    # ------------------------------------------------------------------

    def _tick(self):
        self._countdown -= 1
        self._update_countdown()
        if self._countdown <= 0:
            self._timer.stop()
            self.close()

    def _update_countdown(self):
        if self._auto_close_enabled and self._auto_close > 0:
            self.countdown_label.setText(f"{self._countdown}s 后关闭")
        else:
            self.countdown_label.setText("")

    def _manual_close(self):
        self._timer.stop()
        self.close()

    # ------------------------------------------------------------------
    # Enter/leave for close button visibility
    # ------------------------------------------------------------------

    def enterEvent(self, event):
        self.close_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.close_btn.hide()
        super().leaveEvent(event)
