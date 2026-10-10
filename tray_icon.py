"""System tray icon with right-click menu."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from config import APP_NAME


def create_app_icon() -> QIcon:
    """Create a simple application icon programmatically (no .ico file needed).

    Draws a dark rounded square with a white '译' character.
    """
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark blue rounded background
    painter.setBrush(QColor(30, 80, 160))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 12, 12)

    # White "译" character
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Microsoft YaHei", 28, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignCenter, "译")
    painter.end()
    return QIcon(pix)

class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu.

    Signals:
        translate_triggered — user clicked "翻译" or double-clicked the icon
        settings_triggered  — user clicked "设置"
        reselect_triggered  — user clicked "重新选择"
        quit_triggered      — user clicked "退出"
    """

    translate_triggered = Signal()
    settings_triggered = Signal()
    reselect_triggered = Signal()
    quit_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(create_app_icon(), parent)
        self.setToolTip(APP_NAME)
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()

        self.action_translate = QAction("翻译", menu)
        self.action_translate.triggered.connect(self.translate_triggered)
        menu.addAction(self.action_translate)

        self.action_reselect = QAction("重新选择", menu)
        self.action_reselect.triggered.connect(self.reselect_triggered)
        menu.addAction(self.action_reselect)

        self.action_settings = QAction("设置", menu)
        self.action_settings.triggered.connect(self.settings_triggered)
        menu.addAction(self.action_settings)

        menu.addSeparator()

        self.action_quit = QAction("退出", menu)
        self.action_quit.triggered.connect(self.quit_triggered)
        menu.addAction(self.action_quit)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        """Double-click the tray icon to trigger translation."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.translate_triggered.emit()

    def show_message(self, title: str, message: str):
        """Show a balloon notification from the tray."""
        self.showMessage(title, message, QSystemTrayIcon.Information, 3000)
