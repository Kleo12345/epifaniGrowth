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
    jd.project_day = lambda: 9  # calendar day 9: fam=build, hook=STRUGGLE, kind=journey
    fake_script = types.SimpleNamespace(day=9, caption="test caption", voiceover="hi")
    jd.generate_journey_script = lambda picks, milestone, hook_style=None, content_frame=None: fake_script
    jd.build_journey_video = lambda picks, script: {"video_path": "/tmp/fake.mp4"}

    chat = {"id": fake_tg.chat_id}

    # 1. The daily job generates straight from the calendar — no prompt, no wait —
    #    and no-ops on a second call the same day.
    jd.job_generate_daily()
    state = jd._load_state()
    assert state["status"] == "awaiting_approval", state
    assert state["calendar_day"] == 9, state
    assert state["fam"] == "build" and state["hook"] == "STRUGGLE", state
    assert state["kind"] == "journey", state
    assert "data pipeline" in state["milestone"], state
    assert len(fake_tg.sent_videos) == 1

    jd.job_generate_daily()
    assert len(fake_tg.sent_videos) == 1, "should not regenerate same day"

    # 2. Text sent while awaiting approval is stored as feedback, not a new milestone.
    jd.handle_update({"message": {"chat": chat, "text": "make it punchier"}})
    state = jd._load_state()
    assert state["feedback"] == "make it punchier", state

    # 3. Regenerate consumes the feedback and sends a second video; feedback clears.
    jd.handle_update({
        "callback_query": {
            "id": "1", "data": "regenerate",
            "message": {"message_id": 99, "chat": chat},
        }
    })
    state = jd._load_state()
    assert len(fake_tg.sent_videos) == 2
    assert state["feedback"] is None, state

    # 4. Approve marks the day done.
    jd.handle_update({
        "callback_query": {
            "id": "2", "data": "approve",
            "message": {"message_id": 99, "chat": chat},
        }
    })
    state = jd._load_state()
    assert state["status"] == "approved", state

    # 5. Updates from a different chat id are ignored (single-user gate).
    jd.handle_update({"message": {"chat": {"id": "999"}, "text": "nope"}})
    state = jd._load_state()
    assert state["status"] == "approved", "foreign chat must not touch state"

    jd.STATE_PATH.unlink(missing_ok=True)

    # 6. Weekly record-check-in days (e.g. day 14) route to the track-record script
    #    using real performance data, not a calendar topic/milestone.
    jd.project_day = lambda: 14
    jd.fetch_performance = lambda: {"sample": 20, "hitRate": 0.7}
    jd.fetch_recent_winners = lambda: []
    record_calls = []

    def fake_track_record(perf, winners, hook_style=None, revision_note=""):
        record_calls.append((perf, revision_note))
        return types.SimpleNamespace(day=14, caption="record caption", voiceover="hi")

    jd.generate_track_record_script = fake_track_record
    jd.job_generate_daily()
    state = jd._load_state()
    assert state["kind"] == "record", state
    assert record_calls and record_calls[0][0]["sample"] == 20

    jd.STATE_PATH.unlink(missing_ok=True)
    print("OK — journey_daemon state machine behaves as expected")


if __name__ == "__main__":
    demo()
