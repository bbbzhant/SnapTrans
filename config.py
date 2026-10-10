"""Configuration management: defaults, load/save config.json next to the exe/script."""

import json
import os
import sys

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "target_language": "简体中文",
    "hotkey": "ctrl+alt+q",
    "opacity": 0.9,
    "auto_close_enabled": True,
    "auto_close_seconds": 10,
    "timeout": 30,
    # Remembered selection: "region" or "window"
    "last_mode": None,
    "last_region": None,       # [x1, y1, x2, y2] in virtual-screen coords
    "last_window_title": None,
    "last_window_class": None,
}

APP_NAME = "闪译"
APP_VERSION = "1.0"

# Prompt sent to the vision model alongside the screenshot.
TRANSLATION_PROMPT = (
    "请识别图片中的所有文字并翻译成{language}。\n"
    "要求：\n"
    "1. 只输出译文本身，不要任何解释或额外说明\n"
    "2. 保持原文的换行和段落结构\n"
    "3. 游戏术语和口语要翻译得自然流畅，不要逐字硬翻"
)


def get_config_path() -> str:
    """Return the path to config.json, next to the exe (frozen) or this script."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "config.json")


def load_config() -> dict:
    """Load config.json and merge with defaults. Returns a new dict."""
    config = DEFAULT_CONFIG.copy()
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, IOError):
            pass  # Ignore corrupt config, use defaults
    return config


def save_config(config: dict) -> None:
    """Write config dict to config.json with UTF-8 encoding."""
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
