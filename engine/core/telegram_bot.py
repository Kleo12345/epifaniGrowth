"""
Minimal Telegram Bot API client — just the calls journey_daemon.py needs.

No python-telegram-bot dependency: this is ~10 thin wrappers over `requests`
(already a project dependency), which is all a single-user approve/regenerate
bot needs. Long-polling via getUpdates, no webhook server required.
"""
import json
import os

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


def send_message(text: str, reply_markup: dict | None = None) -> dict:
    payload = {"chat_id": own_chat_id(), "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(_url("sendMessage"), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["result"]


def send_video(path: str, caption: str, reply_markup: dict | None = None) -> dict:
    data = {"chat_id": own_chat_id(), "caption": caption[:1024]}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    with open(path, "rb") as f:
        r = requests.post(_url("sendVideo"), data=data, files={"video": f}, timeout=180)
    r.raise_for_status()
    return r.json()["result"]


def edit_reply_markup(message_id: int, reply_markup: dict | None = None) -> dict:
    payload = {
        "chat_id": own_chat_id(),
        "message_id": message_id,
        "reply_markup": reply_markup or {"inline_keyboard": []},
    }
    r = requests.post(_url("editMessageReplyMarkup"), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def answer_callback(callback_id: str, text: str | None = None) -> None:
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    requests.post(_url("answerCallbackQuery"), json=payload, timeout=30)


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(_url("getUpdates"), params=params, timeout=timeout + 10)
    r.raise_for_status()
    return r.json()["result"]
