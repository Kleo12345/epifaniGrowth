"""
Tests for telegram_bot.py token redaction.

Run: cd growth/engine && python -m pytest core/test_telegram_bot.py -q
"""
import os
import sys

import pytest
import requests

# Ensure we test the local module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from core.telegram_bot import (
    TelegramError,
    _redact,
    send_message,
    answer_callback,
    _call,
)


class TestRedact:
    """Tests for the _redact helper."""

    def test_redact_with_token_set(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        msg = "https://api.telegram.org/bot123456:ABC-secret_token/sendMessage"
        assert _redact(msg) == "https://api.telegram.org/bot<redacted>/sendMessage"

    def test_redact_with_token_unset(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        msg = "https://api.telegram.org/bot123456:ABC-secret_token/sendMessage"
        # Falls back to regex pattern
        assert _redact(msg) == "https://api.telegram.org/bot<redacted>/sendMessage"

    def test_redact_empty_string(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        assert _redact("") == ""
        assert _redact(None) is None  # type: ignore

    def test_redact_no_token_in_text(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        msg = "Just a normal error message"
        assert _redact(msg) == "Just a normal error message"

    def test_redact_multiple_occurrences(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        msg = "bot123456:ABC-secret_token and bot123456:ABC-secret_token again"
        assert _redact(msg) == "bot<redacted> and bot<redacted> again"

    def test_redact_regex_fallback(self, monkeypatch):
        """Test the regex fallback catches any bot<token> pattern."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        # Different token than what would be in env
        msg = "Connection to bot999999:XYZ-other_token failed"
        assert _redact(msg) == "Connection to bot<redacted> failed"


class TestTelegramError:
    """Tests for the TelegramError exception."""

    def test_telegram_error_inherits_from_request_exception(self):
        err = TelegramError("test message")
        assert isinstance(err, requests.RequestException)
        assert str(err) == "test message"

    def test_telegram_error_has_status_code(self):
        err = TelegramError("test message", status_code=400)
        assert err.status_code == 400


class TestCallHelper:
    """Tests for the _call internal helper."""

    def test_http_error_redacted_and_wrapped(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")

        def fake_post(*args, **kwargs):
            resp = requests.Response()
            resp.status_code = 400
            resp.url = "https://api.telegram.org/bot123456:ABC-secret_token/sendMessage"
            # raise_for_status will raise HTTPError
            resp.raise_for_status = lambda: (_ for _ in ()).throw(
                requests.HTTPError("400 Client Error: Bad Request for url: https://api.telegram.org/bot123456:ABC-secret_token/sendMessage", response=resp)
            )
            return resp

        monkeypatch.setattr(requests, "post", fake_post)

        with pytest.raises(TelegramError) as exc_info:
            _call(requests.post, "sendMessage", json={"chat_id": "1", "text": "hi"})

        err = exc_info.value
        # Token must not appear in the error message
        assert "ABC-secret_token" not in str(err)
        assert "ABC-secret_token" not in repr(err)
        assert "<redacted>" in str(err)
        # Must be TelegramError
        assert isinstance(err, TelegramError)
        # No chaining
        assert err.__cause__ is None
        assert err.__suppress_context__ is True
        # status_code preserved
        assert err.status_code == 400

    def test_connection_error_redacted(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")

        def fake_post(*args, **kwargs):
            raise requests.ConnectionError(
                "HTTPConnectionPool(host='api.telegram.org', port=443): "
                "Max retries exceeded with url: /bot123456:ABC-secret_token/getUpdates"
            )

        monkeypatch.setattr(requests, "post", fake_post)

        with pytest.raises(TelegramError) as exc_info:
            _call(requests.post, "getUpdates")

        err = exc_info.value
        assert "ABC-secret_token" not in str(err)
        assert "ABC-secret_token" not in repr(err)
        assert "<redacted>" in str(err)
        assert isinstance(err, TelegramError)
        assert err.__cause__ is None
        assert err.status_code is None  # No response for connection errors


class TestAnswerCallback:
    """Tests for answer_callback behaviour."""

    def test_answer_callback_bad_status_does_not_raise(self, monkeypatch):
        """answer_callback uses check=False, so bad HTTP status should not raise."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

        def fake_post(*args, **kwargs):
            resp = requests.Response()
            resp.status_code = 400
            resp.url = "https://api.telegram.org/bot123456:ABC-secret_token/answerCallbackQuery"
            # No raise_for_status call because check=False
            return resp

        monkeypatch.setattr(requests, "post", fake_post)

        # Should not raise
        answer_callback("callback_123", "some text")

    def test_answer_callback_connection_error_raises_redacted(self, monkeypatch):
        """Connection errors are still redacted even with check=False."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

        def fake_post(*args, **kwargs):
            raise requests.ConnectionError(
                "Max retries exceeded with url: /bot123456:ABC-secret_token/answerCallbackQuery"
            )

        monkeypatch.setattr(requests, "post", fake_post)

        with pytest.raises(TelegramError) as exc_info:
            answer_callback("callback_123")

        err = exc_info.value
        assert "ABC-secret_token" not in str(err)
        assert "<redacted>" in str(err)


class TestSendMessageSuccess:
    """Tests for the success path of send_message."""

    def test_send_message_returns_result(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

        def fake_post(*args, **kwargs):
            resp = requests.Response()
            resp.status_code = 200
            resp._content = b'{"ok": true, "result": {"message_id": 42, "text": "hi"}}'
            return resp

        monkeypatch.setattr(requests, "post", fake_post)

        result = send_message("hi")
        assert result == {"message_id": 42, "text": "hi"}

    def test_send_message_long_text_chunks(self, monkeypatch):
        """Long texts are chunked; keyboard goes on last chunk."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-secret_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

        calls = []

        def fake_post(*args, **kwargs):
            calls.append(kwargs.get("json", {}))
            resp = requests.Response()
            resp.status_code = 200
            resp._content = b'{"ok": true, "result": {"message_id": 42}}'
            return resp

        monkeypatch.setattr(requests, "post", fake_post)

        long_text = "x" * 5000  # Two chunks: 4000 + 1000
        keyboard = {"inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]}
        send_message(long_text, reply_markup=keyboard)

        assert len(calls) == 2
        # First chunk: no keyboard
        assert "reply_markup" not in calls[0]
        # Second chunk: has keyboard
        assert calls[1].get("reply_markup") == keyboard