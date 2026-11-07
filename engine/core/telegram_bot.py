"""
Minimal Telegram Bot API client — just the calls journey_daemon.py needs.

No python-telegram-bot dependency: this is ~10 thin wrappers over `requests`
(already a project dependency), which is all a single-user approve/regenerate
bot needs. Long-polling via getUpdates, no webhook server required.
"""
import json
import os
import re
from typing import Callable

import requests


_API = "https://api.telegram.org/bot{token}/{method}"

APPROVE_KEYBOARD = {
    "inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": "approve"},
        {"text": "🔁 Regenerate", "callback_data": "regenerate"},
    ]]
}
RETRY_KEYBOARD = {
    "inline_keyboard": [[{"text": "🔁 Regenerate", "callback_data": "regenerate"}]]
}
RETRY_POST_KEYBOARD = {
    "inline_keyboard": [[{"text": "📤 Retry failed platforms", "callback_data": "retry_post"}]]
}
POST_TICKETS_KEYBOARD = {
    "inline_keyboard": [[{"text": "📤 Post as Instagram Stories", "callback_data": "post_tickets"}]]
}


def is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip()) and bool(own_chat_id())


def own_chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    return token


def _url(method: str) -> str:
    return _API.format(token=_token(), method=method)


# ---- Token redaction --------------------------------------------------------

_TOKEN_PATTERN = re.compile(r"bot\d+:[A-Za-z0-9_-]+")


def _redact(text: str) -> str:
    """Replace any Telegram bot token in text with '<redacted>'."""
    if not text:
        return text
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        text = text.replace(token, "<redacted>")
    # Fallback: catch any bot<token> pattern in URLs or error messages
    return _TOKEN_PATTERN.sub("bot<redacted>", text)


class TelegramError(requests.RequestException):
    """Raised when a Telegram API call fails. Message is always redacted.
    Does not chain the original exception (from None), and does not attach
    response/request objects whose .url would leak the token.
    """
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _call(http_method: Callable, method: str, *, check: bool = True, **kwargs) -> requests.Response:
    """Internal helper: perform the request and redact any error."""
    try:
        r = http_method(_url(method), **kwargs)
        if check:
            r.raise_for_status()
        return r
    except requests.RequestException as e:
        status = e.response.status_code if e.response is not None else None
        raise TelegramError(_redact(str(e)), status) from None


# ---- Public API -------------------------------------------------------------

def send_message(text: str, reply_markup: dict | None = None) -> dict:
    """Long texts are split into 4000-char messages (Telegram's limit is 4096);
    the keyboard goes on the last one."""
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [""]
    last_response = None
    for i, chunk in enumerate(chunks):
        payload = {"chat_id": own_chat_id(), "text": chunk}
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        r = _call(requests.post, "sendMessage", json=payload, timeout=30)
        last_response = r
    return last_response.json()["result"]


def send_video(path: str, caption: str, reply_markup: dict | None = None) -> dict:
    data = {"chat_id": own_chat_id(), "caption": caption[:1024]}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    with open(path, "rb") as f:
        r = _call(requests.post, "sendVideo", data=data, files={"video": f}, timeout=180)
    return r.json()["result"]


def send_photos(paths: list, caption: str = "") -> None:
    """Albums of up to 10 (Telegram's limit); a lone photo goes via sendPhoto. Caption on the first."""
    for start in range(0, len(paths), 10):
        chunk = paths[start:start + 10]
        cap = caption[:1024] if start == 0 else ""
        files = {f"p{i}": open(p, "rb") for i, p in enumerate(chunk)}
        try:
            if len(chunk) == 1:
                r = _call(requests.post, "sendPhoto", timeout=120, files={"photo": files["p0"]},
                          data={"chat_id": own_chat_id(), "caption": cap})
            else:
                media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(chunk))]
                media[0]["caption"] = cap
                r = _call(requests.post, "sendMediaGroup", timeout=120, files=files,
                          data={"chat_id": own_chat_id(), "media": json.dumps(media)})
        finally:
            for f in files.values():
                f.close()
        r.raise_for_status()


def edit_reply_markup(message_id: int, reply_markup: dict | None = None) -> dict:
    payload = {
        "chat_id": own_chat_id(),
        "message_id": message_id,
        "reply_markup": reply_markup or {"inline_keyboard": []},
    }
    r = _call(requests.post, "editMessageReplyMarkup", json=payload, timeout=30)
    return r.json()


def answer_callback(callback_id: str, text: str | None = None) -> None:
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    # check=False keeps current behaviour: no raise on bad HTTP status,
    # but connection/timeout errors are still redacted via _call
    _call(requests.post, "answerCallbackQuery", json=payload, timeout=30, check=False)


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    r = _call(requests.get, "getUpdates", params=params, timeout=timeout + 10)
    return r.json()["result"]