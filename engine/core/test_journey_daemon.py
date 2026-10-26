"""
Assert-based self-check for journey_daemon.py's approval state machine.
No network, no Gemini, no ffmpeg — everything is monkeypatched. Run with:
  python core/test_journey_daemon.py
"""
import datetime as pydatetime
import sys
import types
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import journey_daemon as jd


class _FixedNow:
    """Stand-in for the `datetime` name journey_daemon imports — only `.now()` is used,
    and it always returns this fixed, caller-supplied instant."""
    def __init__(self, fixed):
        self._fixed = fixed

    def now(self, tz=None):
        return self._fixed


class FakeTG:
    APPROVE_KEYBOARD = {"inline_keyboard": [["approve", "regenerate"]]}
    RETRY_KEYBOARD = {"inline_keyboard": [["regenerate"]]}
    RETRY_POST_KEYBOARD = {"inline_keyboard": [["retry_post"]]}

    def __init__(self, chat_id="12345"):
        self.chat_id = chat_id
        self.sent_messages = []
        self.sent_videos = []
        self.edited = []

    def own_chat_id(self):
        return self.chat_id

    def send_message(self, text, reply_markup=None):
        self.sent_messages.append(text)
        self.last_markup = reply_markup
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
    jd.platform_captions = lambda script: {"instagram": {"caption": "ig cap", "hashtags": "#ai"}}
    jd.configured_platforms = lambda: ["instagram"]
    jd.project_day = lambda: 9  # calendar day 9: fam=build, hook=STRUGGLE, kind=journey
    fake_script = types.SimpleNamespace(day=9, milestone="m", caption="test caption",
                                        hashtags="#ai", voiceover="hi")
    jd.generate_journey_script = lambda picks, milestone, hook_style=None, content_frame=None, **kw: fake_script
    fam_calls = []

    def fake_build(picks, script, fam=None):
        fam_calls.append(fam)
        return {"video_path": "/tmp/fake.mp4"}

    jd.build_journey_video = fake_build

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
    assert fam_calls[-1] == "build", "day 9's fam should drive the background palette"

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

    # 4. Approve marks the day done and posts to every connected platform; a failed
    #    platform gets a retry button, and retry only re-posts the ones that failed.
    assert state["script"]["caption"] == "test caption", "script must be saved for posting"
    publish_calls = []
    x_works = {"ok": False}

    def fake_publish(video_path, script, meta, platforms, captions=None):
        assert captions and "instagram" in captions, "must post the previewed captions"
        publish_calls.append(list(platforms))
        return {p: ({"ok": True, "url": f"https://{p}/1", "caption": "c", "error": None}
                    if p != "x" or x_works["ok"] else
                    {"ok": False, "url": None, "caption": "c", "error": "boom"}) for p in platforms}

    jd.publish = fake_publish
    jd.configured_platforms = lambda: ["instagram", "x"]
    jd.handle_update({
        "callback_query": {
            "id": "2", "data": "approve",
            "message": {"message_id": 99, "chat": chat},
        }
    })
    state = jd._load_state()
    assert state["status"] == "approved", state
    assert publish_calls == [["instagram", "x"]], publish_calls
    assert state["posted"] == {"instagram": "https://instagram/1"}, state
    assert fake_tg.last_markup == FakeTG.RETRY_POST_KEYBOARD, "failed platform → retry button"

    x_works["ok"] = True
    jd.handle_update({"callback_query": {"id": "3", "data": "retry_post",
                                         "message": {"message_id": 100, "chat": chat}}})
    state = jd._load_state()
    assert publish_calls[-1] == ["x"], "retry must only re-post the failed platform"
    assert set(state["posted"]) == {"instagram", "x"}, state
    assert fake_tg.last_markup is None

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

    # 7. A day with a quoted calendar topic (day 32) builds and sends the same as
    #    any other journey day — no on-screen card logic to special-case anymore.
    jd.project_day = lambda: 32
    jd.generate_journey_script = lambda picks, milestone, hook_style=None, content_frame=None, **kw: fake_script
    jd.job_generate_daily()
    assert fam_calls[-1] == "human", "day 32's fam should drive the background palette"
    jd.STATE_PATH.unlink(missing_ok=True)

    # 8. Catch-up: a cron trigger only fires while the process is alive, so if the
    #     PC was off through today's 08:50 slot, startup must generate it immediately
    #     instead of silently waiting for tomorrow.
    jd.project_day = lambda: 9
    tz = ZoneInfo(jd.TIMEZONE)
    before = len(fake_tg.sent_videos)

    # Before the slot: nothing to catch up on yet, the normal cron will fire it.
    jd.datetime = _FixedNow(pydatetime.datetime(2026, 10, 4, 7, 0, tzinfo=tz))
    jd._catch_up_if_missed()
    assert len(fake_tg.sent_videos) == before, "before today's slot — no catch-up generation"
    jd.STATE_PATH.unlink(missing_ok=True)

    # After the slot, nothing generated yet (simulates the PC having been off at 08:50):
    # catch-up must run the job immediately.
    jd.datetime = _FixedNow(pydatetime.datetime(2026, 10, 4, 10, 0, tzinfo=tz))
    jd._catch_up_if_missed()
    assert len(fake_tg.sent_videos) == before + 1, "past today's slot with nothing generated — must catch up"
    state = jd._load_state()
    assert state["calendar_day"] == 9 and state["status"] == "awaiting_approval", state

    # Already generated today (state is no longer idle) — catch-up must not re-fire.
    jd._catch_up_if_missed()
    assert len(fake_tg.sent_videos) == before + 1, "already generated today — catch-up must be idempotent"
    jd.STATE_PATH.unlink(missing_ok=True)

    # 9. Crash recovery: a build that throws (e.g. no network after wake) must not
    #    leave the day stuck on "generating" — it goes back to idle for the retry job,
    #    and parks in "error" after MAX_CRASH_RETRIES so it stops burning credits.
    def boom(picks, script, fam=None):
        raise ConnectionError("no network")

    jd.build_journey_video = boom
    for attempt in range(1, jd.MAX_CRASH_RETRIES):
        jd._catch_up_if_missed()
        state = jd._load_state()
        assert state["status"] == "idle" and state["crashes"] == attempt, state
    jd._catch_up_if_missed()
    state = jd._load_state()
    assert state["status"] == "error", "gives up after MAX_CRASH_RETRIES"
    jd._catch_up_if_missed()
    assert jd._load_state()["crashes"] == jd.MAX_CRASH_RETRIES, "no retries once parked in error"
    jd.STATE_PATH.unlink(missing_ok=True)

    # Gate misses are retried with fresh takes; only a persistent miss surfaces.
    takes = []

    def misses_then(passes_on):
        def gen():
            takes.append(1)
            if len(takes) < passes_on:
                raise jd.ScriptQualityError({"avg": 8.3, "hook": 7, "safe": 9}, "weak hook", "vo", 1)
            return "script"
        return gen

    assert jd._until_gate_clears(misses_then(3)) == "script" and len(takes) == 3
    takes.clear()
    try:
        jd._until_gate_clears(misses_then(99))
        raise AssertionError("should give up")
    except jd.ScriptQualityError:
        assert len(takes) == jd.MAX_GATE_ATTEMPTS

    print("OK — journey_daemon state machine behaves as expected")


if __name__ == "__main__":
    demo()
