"""Settings dialog — API config, hotkey, appearance, timing.

All settings are saved to config.json on accept.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QWidget,
)

from config import APP_NAME, APP_VERSION, load_config, save_config


class HotkeyLineEdit(QLineEdit):
    """A text field that captures the next key combination when focused.

    Displays the current hotkey as text (e.g. "ctrl+alt+q"). When the user
    presses a key combination while focused, it captures and displays it in
    keyboard-library format.
    """

    # Mapping from Qt key modifiers to keyboard-library names
    MOD_MAP = {
        Qt.CTRL: "ctrl",
        Qt.SHIFT: "shift",
        Qt.ALT: "alt",
        Qt.META: "win",
    }

    def __init__(self, initial: str = "ctrl+alt+q", parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setText(initial)
        self.setPlaceholderText("点击此处后按下快捷键")
        self.setStyleSheet("QLineEdit { font-size: 13px; }")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()

        # Ignore lone modifier presses
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        parts = []
        for mod_flag, name in self.MOD_MAP.items():
            if mods & mod_flag:
                parts.append(name)

        # Key name
        key_name = _qt_key_to_name(key)
        if key_name:
            parts.append(key_name)

        if parts:
            self.setText("+".join(parts))


def _qt_key_to_name(key: int) -> str:
    """Convert a Qt key code to a keyboard-library key name."""
    # Letters and digits
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(ord('a') + (key - Qt.Key_A))
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(ord('0') + (key - Qt.Key_0))
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f"f{key - Qt.Key_F1 + 1}"

    SPECIAL = {
        Qt.Key_Space: "space",
        Qt.Key_Return: "enter",
        Qt.Key_Enter: "enter",
        Qt.Key_Tab: "tab",
        Qt.Key_Minus: "-",
        Qt.Key_Equal: "=",
        Qt.Key_BracketLeft: "[",
        Qt.Key_BracketRight: "]",
        Qt.Key_Semicolon: ";",
        Qt.Key_Apostrophe: "'",
        Qt.Key_Comma: ",",
        Qt.Key_Period: ".",
        Qt.Key_Slash: "/",
        Qt.Key_Backslash: "\\",
        Qt.Key_QuoteLeft: "`",
    }
    return SPECIAL.get(key, "")


class SettingsDialog(QDialog):
    """Modal settings dialog. Emits config_changed() when settings are saved."""

    config_changed = Signal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — 设置")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- API settings group ---
        api_group = QGroupBox("API 设置")
        api_form = QFormLayout()
        api_form.setSpacing(8)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        api_form.addRow("API Key:", self.api_key_input)

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.openai.com/v1")
        api_form.addRow("Base URL:", self.base_url_input)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("gpt-4o-mini")
        api_form.addRow("模型:", self.model_input)

        model_hint = QLabel(
            "需要具有视觉能力的大模型。\n"
            "推荐：DeepSeek-v4.1-flash / glm-5.3-flash / kimi-k3 / GPT-4o 系列"
        )
        model_hint.setStyleSheet("color: gray; font-size: 11px;")
        model_hint.setWordWrap(True)
        api_form.addRow("", model_hint)

        self.language_input = QLineEdit()
        self.language_input.setPlaceholderText("简体中文")
        api_form.addRow("目标语言:", self.language_input)

        api_group.setLayout(api_form)
        layout.addWidget(api_group)

        # --- Hotkey group ---
        hotkey_group = QGroupBox("快捷键")
        hotkey_layout = QHBoxLayout()
        self.hotkey_input = HotkeyLineEdit(self.config.get("hotkey", "ctrl+alt+q"))
        hotkey_layout.addWidget(self.hotkey_input)
        hotkey_hint = QLabel("点击输入框后按下组合键")
        hotkey_hint.setStyleSheet("color: gray; font-size: 11px;")
        hotkey_layout.addWidget(hotkey_hint)
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)

        # --- Display group ---
        display_group = QGroupBox("显示设置")
        display_form = QFormLayout()
        display_form.setSpacing(8)

        self.opacity_input = QDoubleSpinBox()
        self.opacity_input.setRange(0.3, 1.0)
        self.opacity_input.setSingleStep(0.1)
        self.opacity_input.setDecimals(1)
        display_form.addRow("小窗透明度:", self.opacity_input)

        # Auto-close row: checkbox + seconds spinbox on one line
        auto_close_widget = QWidget()
        auto_close_layout = QHBoxLayout(auto_close_widget)
        auto_close_layout.setContentsMargins(0, 0, 0, 0)
        self.auto_close_enabled_checkbox = QCheckBox("启用自动关闭")
        self.auto_close_input = QSpinBox()
        self.auto_close_input.setRange(1, 300)
        self.auto_close_input.setSuffix(" 秒")
        auto_close_layout.addWidget(self.auto_close_enabled_checkbox)
        auto_close_layout.addWidget(self.auto_close_input)
        # Toggle the spinbox enabled state based on checkbox
        self.auto_close_enabled_checkbox.toggled.connect(self.auto_close_input.setEnabled)
        display_form.addRow("自动关闭:", auto_close_widget)

        display_group.setLayout(display_form)
        layout.addWidget(display_group)

        # --- Network group ---
        net_group = QGroupBox("网络设置")
        net_form = QFormLayout()
        net_form.setSpacing(8)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        self.timeout_input.setSuffix(" 秒")
        net_form.addRow("请求超时:", self.timeout_input)

        net_group.setLayout(net_form)
        layout.addWidget(net_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setDefault(True)
        save_btn.setMinimumWidth(80)
        save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_values(self):
        """Populate form fields from the config dict."""
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.base_url_input.setText(self.config.get("base_url", "https://api.openai.com/v1"))
        self.model_input.setText(self.config.get("model", "gpt-4o-mini"))
        self.language_input.setText(self.config.get("target_language", "简体中文"))
        self.hotkey_input.setText(self.config.get("hotkey", "ctrl+alt+q"))
        self.opacity_input.setValue(self.config.get("opacity", 0.9))
        self.auto_close_enabled_checkbox.setChecked(self.config.get("auto_close_enabled", True))
        self.auto_close_input.setValue(self.config.get("auto_close_seconds", 10))
        self.auto_close_input.setEnabled(self.auto_close_enabled_checkbox.isChecked())
        self.timeout_input.setValue(self.config.get("timeout", 30))

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        """Read form values into config and save to disk."""
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["base_url"] = self.base_url_input.text().strip() or "https://api.openai.com/v1"
        self.config["model"] = self.model_input.text().strip() or "gpt-4o-mini"
        self.config["target_language"] = self.language_input.text().strip() or "简体中文"
        self.config["hotkey"] = self.hotkey_input.text().strip() or "ctrl+alt+q"
        self.config["opacity"] = self.opacity_input.value()
        self.config["auto_close_enabled"] = self.auto_close_enabled_checkbox.isChecked()
        self.config["auto_close_seconds"] = self.auto_close_input.value()
        self.config["timeout"] = self.timeout_input.value()

        save_config(self.config)
        self.config_changed.emit()
        self.accept()
