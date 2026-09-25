"""
Assert-based self-check for journey_daemon.py's approval state machine.
No network, no Gemini, no ffmpeg — everything is monkeypatched. Run with:
  python core/test_journey_daemon.py
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import journey_daemon as jd


class FakeTG:
    APPROVE_KEYBOARD = {"inline_keyboard": [["approve", "regenerate"]]}
    RETRY_KEYBOARD = {"inline_keyboard": [["regenerate"]]}

    def __init__(self, chat_id="12345"):
        self.chat_id = chat_id
        self.sent_messages = []
        self.sent_videos = []
        self.edited = []

    def own_chat_id(self):
        return self.chat_id

    def send_message(self, text, reply_markup=None):
        self.sent_messages.append(text)
        return {"message_id": 1}

    def send_video(self, path, caption, reply_markup=None):
        self.sent_videos.append((path, caption))
        return {"message_id": 99}

    def edit_reply_markup(self, message_id, reply_markup=None):
        self.edited.append(message_id)

    def answer_callback(self, callback_id, text=None):
        pass


def demo():
    fake_tg = FakeTG()
    jd.tg = fake_tg  # module-level name rebind — every `tg.xxx(...)` call in journey_daemon resolves this

    jd.STATE_PATH = Path("/tmp/_journey_daemon_test_state.json")
    jd.STATE_PATH.unlink(missing_ok=True)

    jd.fetch_picks = lambda **kw: []
    fake_script = types.SimpleNamespace(day=1, caption="test caption", voiceover="hi")
    jd.generate_journey_script = lambda picks, milestone: fake_script
    jd.build_journey_video = lambda picks, script: {"video_path": "/tmp/fake.mp4"}

    chat = {"id": fake_tg.chat_id}

    # 1. Daily prompt fires once, then no-ops on a second call the same day.
    jd.job_prompt_milestone()
    state = jd._load_state()
    assert state["status"] == "awaiting_milestone", state
    assert len(fake_tg.sent_messages) == 1

    jd.job_prompt_milestone()
    assert len(fake_tg.sent_messages) == 1, "should not re-prompt same day"

    # 2. A milestone reply triggers generation and a video with buttons.
    jd.handle_update({"message": {"chat": chat, "text": "fixed the parser"}})
    state = jd._load_state()
    assert state["status"] == "awaiting_approval", state
    assert state["milestone"] == "fixed the parser"
    assert len(fake_tg.sent_videos) == 1

    # 3. Text sent while awaiting approval is stored as feedback, not a new milestone.
    jd.handle_update({"message": {"chat": chat, "text": "make it punchier"}})
    state = jd._load_state()
    assert state["feedback"] == "make it punchier", state

    # 4. Regenerate consumes the feedback and sends a second video; feedback clears.
    jd.handle_update({
        "callback_query": {
            "id": "1", "data": "regenerate",
            "message": {"message_id": 99, "chat": chat},
        }
    })
    state = jd._load_state()
    assert len(fake_tg.sent_videos) == 2
    assert state["feedback"] is None, state

    # 5. Approve marks the day done.
    jd.handle_update({
        "callback_query": {
            "id": "2", "data": "approve",
            "message": {"message_id": 99, "chat": chat},
        }
    })
    state = jd._load_state()
    assert state["status"] == "approved", state

    # 6. Updates from a different chat id are ignored (single-user gate).
    jd.handle_update({"message": {"chat": {"id": "999"}, "text": "nope"}})
    state = jd._load_state()
    assert state["status"] == "approved", "foreign chat must not touch state"

    jd.STATE_PATH.unlink(missing_ok=True)
    print("OK — journey_daemon state machine behaves as expected")


if __name__ == "__main__":
    demo()
