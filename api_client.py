"""OpenAI-compatible vision API client for screenshot translation."""

import base64
import io

import requests
from PIL import Image
from PySide6.QtCore import QThread, Signal

from config import TRANSLATION_PROMPT


class TranslationError(Exception):
    """Raised when the API call fails with a user-facing message."""


def image_to_base64(img: Image.Image) -> str:
    """Encode a PIL Image to a base64 PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def translate_image(image_b64: str, config: dict) -> str:
    """Call the vision API and return the translated text.

    Raises TranslationError with a user-friendly message on failure.
    """
    base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    api_key = config.get("api_key", "")
    model = config.get("model", "gpt-4o-mini")
    language = config.get("target_language", "简体中文")
    timeout = config.get("timeout", 30)

    if not api_key:
        raise TranslationError("未设置 API Key，请先在设置中填写。")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt = TRANSLATION_PROMPT.format(language=language)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                        },
                    },
                ],
            }
        ],
        "max_tokens": 2000,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        raise TranslationError(f"请求超时（{timeout}秒），请检查网络或增加超时时间。")
    except requests.exceptions.ConnectionError:
        raise TranslationError("网络连接失败，请检查网络或 Base URL 是否正确。")
    except requests.exceptions.RequestException as e:
        raise TranslationError(f"网络请求失败：{e}")

    if resp.status_code == 401:
        raise TranslationError("API Key 无效或已过期，请检查设置。")
    if resp.status_code == 402:
        raise TranslationError("账户余额不足，请充值。")
    if resp.status_code == 429:
        raise TranslationError("请求过于频繁或额度已用完，请稍后重试。")
    if resp.status_code >= 400:
        # Try to extract error message from response body
        try:
            err = resp.json()
            err_msg = err.get("error", {}).get("message", resp.text[:200])
        except Exception:
            err_msg = resp.text[:200]
        raise TranslationError(f"API 错误（{resp.status_code}）：{err_msg}")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        raise TranslationError(f"解析 API 响应失败：{e}")


class TranslateWorker(QThread):
    """Run translate_image in a background thread to avoid blocking the UI.

    Emits:
        success(str) — translated text
        error(str)   — user-facing error message
    """

    success = Signal(str)
    error = Signal(str)

    def __init__(self, image_b64: str, config: dict):
        super().__init__()
        self._image_b64 = image_b64
        self._config = config

    def run(self):
        try:
            result = translate_image(self._image_b64, self._config)
            self.success.emit(result)
        except TranslationError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")
