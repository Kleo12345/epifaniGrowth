#!/usr/bin/env python3
"""
Telegram-driven Founder's Journey daemon — fully automated against the Plan A+
content calendar (core/content_calendar.py, 44 days).

Every day at 08:50 Europe/Athens the daemon looks up today's calendar day
(core.script_generator.project_day), generates that day's video straight from
the calendar's topic/hook/family — no prompt, no waiting on a reply — and
sends it to Telegram with Approve/Regenerate buttons. Send any text before
tapping Regenerate and it's used as a rewrite note for the next take; tap
Regenerate with no text and it just takes another pass at the same topic.
Approve just marks the video done — posting is still manual (dashboard or
`main.py --post-social`), by design. Once day 45 arrives (the calendar is
exhausted) it falls back to asking what you built, same as before.

Run with:
  conda activate epifani-growth
  python journey_daemon.py
Or install as a systemd --user unit — see epifani-journey.service.

# ponytail: no crash-recovery for a restart mid-"generating" — if the
# process dies while a video is being built, journey_state.json is stuck
# on status="generating" until you edit it back to "awaiting_milestone"
# (or delete the file) and restart. Add real recovery if that ever bites.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import telegram_bot as tg
from core.content_calendar import calendar_entry
from core.prediction_fetcher import fetch_picks, fetch_performance, fetch_recent_winners
from core.script_generator import (
    CONTENT_FRAME_BY_FAM,
    ScriptQualityError,
    generate_journey_script,
    generate_track_record_script,
    hook_style_for_calendar,
    project_day,
)
from core.video_builder import build_journey_video, stop_mpt

TIMEZONE = "Europe/Athens"
PROMPT_HOUR, PROMPT_MINUTE = 8, 50

STATE_PATH = Path(__file__).resolve().parent / "assets" / "output" / "journey_state.json"
OFFSET_PATH = Path(__file__).resolve().parent / "assets" / "output" / "telegram_offset.txt"


# ── State ──────────────────────────────────────────────────────────
# journey_state.json: {date, status, milestone, feedback, video_path,
#                       video_message_id, attempts, calendar_day, fam, hook, kind}
# status: idle | awaiting_milestone | generating | awaiting_approval | error | approved
# kind: "journey" (calendar topic / freeform milestone) | "record" (weekly track-record
#       check-in, built from real performance data instead of a topic)

def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _fresh_state_for_today() -> dict:
    return {
        "date": date.today().isoformat(),
        "status": "idle",
        "milestone": None,
        "feedback": None,
        "video_path": None,
        "video_message_id": None,
        "attempts": 0,
        "calendar_day": None,
        "fam": None,
        "hook": None,
        "kind": None,
    }


def _today_state() -> dict:
    state = _load_state()
    if state.get("date") != date.today().isoformat():
        state = _fresh_state_for_today()
        _save_state(state)
    return state


def _own_chat_id() -> str:
    return tg.own_chat_id()


# ── Pipeline ───────────────────────────────────────────────────────

def _report_quality_failure(state: dict, e: ScriptQualityError) -> None:
    state["status"] = "error"
    state["attempts"] += 1
    _save_state(state)
    tg.send_message(
        f"✗ Script never cleared the quality gate after {e.revisions} rewrite(s) "
        f"(avg {e.scores['avg']}). Tap Regenerate to try again, or send a note first.",
        reply_markup=tg.RETRY_KEYBOARD,
    )


def _generate_and_send(state: dict) -> None:
    state["status"] = "generating"
    _save_state(state)

    feedback = state.get("feedback")
    hook_style = hook_style_for_calendar(state.get("hook"))
    tg.send_message("⚙️ Generating today's video, hang tight...")

    if state.get("kind") == "record":
        try:
            perf = fetch_performance()
            winners = fetch_recent_winners()
        except Exception as e:
            perf, winners = None, []
            print(f"  ⚠ fetch_performance/fetch_recent_winners failed: {e}")
        try:
            script = generate_track_record_script(
                perf, winners, hook_style=hook_style, revision_note=feedback or "",
            )
        except ValueError as e:
            state["status"] = "error"
            state["attempts"] += 1
            _save_state(state)
            tg.send_message(f"✗ No performance data available for today's record check-in: {e}",
                             reply_markup=tg.RETRY_KEYBOARD)
            return
        except ScriptQualityError as e:
            _report_quality_failure(state, e)
            return
        picks = []
    else:
        milestone = state["milestone"]
        if feedback:
            milestone = f"{milestone}\n\n(Revision note for this take: {feedback})"
        try:
            picks = fetch_picks(exclude_corners=True, top=3)
        except Exception as e:
            picks = []
            print(f"  ⚠ fetch_picks failed: {e}")
        try:
            script = generate_journey_script(
                picks, milestone=milestone, hook_style=hook_style,
                content_frame=CONTENT_FRAME_BY_FAM.get(state.get("fam")),
            )
        except ScriptQualityError as e:
            _report_quality_failure(state, e)
            return

    result = build_journey_video(picks, script=script)
    if not result.get("video_path"):
        state["status"] = "error"
        state["attempts"] += 1
        _save_state(state)
        tg.send_message(f"✗ Video build failed: {result.get('error')}", reply_markup=tg.RETRY_KEYBOARD)
        return

    state["video_path"] = result["video_path"]
    state["feedback"] = None
    state["attempts"] += 1
    state["status"] = "awaiting_approval"
    _save_state(state)

    caption = f"Day {script.day} — attempt {state['attempts']}\n\n{script.caption}"
    msg = tg.send_video(result["video_path"], caption=caption, reply_markup=tg.APPROVE_KEYBOARD)
    state["video_message_id"] = msg["message_id"]
    _save_state(state)


def job_generate_daily() -> None:
    """08:50 Athens — auto-generate today's calendar-day video, no prompt needed.

    Falls back to asking for a freeform milestone once Plan A+ (44 days) runs out.
    """
    state = _today_state()
    if state["status"] != "idle":
        return
    day = project_day()
    entry = calendar_entry(day)
    if entry is None:
        state["status"] = "awaiting_milestone"
        _save_state(state)
        tg.send_message(
            f"☀️ Day {day} — Plan A+ calendar (44 days) is done. What did you build/work "
            f"on today? Reply here to generate the video, freeform."
        )
        return

    milestone = entry["topic"]
    if entry.get("note"):
        milestone = f"{milestone} ({entry['note']})"

    state["calendar_day"] = day
    state["fam"] = entry["fam"]
    state["hook"] = entry["hook"]
    state["kind"] = entry["kind"]
    state["milestone"] = milestone
    _save_state(state)
    _generate_and_send(state)


# ── Telegram event handling ────────────────────────────────────────

def handle_update(update: dict) -> None:
    if "callback_query" in update:
        cq = update["callback_query"]
        if str(cq["message"]["chat"]["id"]) != _own_chat_id():
            return
        tg.answer_callback(cq["id"])

        state = _today_state()
        if state["status"] not in ("awaiting_approval", "error"):
            return

        data = cq.get("data")
        if data == "approve":
            state["status"] = "approved"
            _save_state(state)
            tg.edit_reply_markup(cq["message"]["message_id"])
            tg.send_message(f"✅ Approved — {state['video_path']}\nPost it yourself when ready.")
        elif data == "regenerate":
            tg.edit_reply_markup(cq["message"]["message_id"])
            _generate_and_send(state)
        return

    message = update.get("message") or {}
    if "text" not in message:
        return
    if str(message.get("chat", {}).get("id")) != _own_chat_id():
        return

    text = message["text"].strip()
    state = _today_state()

    if state["status"] == "awaiting_milestone":
        state["milestone"] = text
        _save_state(state)
        _generate_and_send(state)
    elif state["status"] in ("awaiting_approval", "error"):
        state["feedback"] = text
        _save_state(state)
        tg.send_message("📝 Got it — tap Regenerate to use this note.")
    # idle / generating / approved: stray message, ignore


# ── Main loop ──────────────────────────────────────────────────────

def _load_offset() -> int | None:
    try:
        return int(OFFSET_PATH.read_text().strip())
    except Exception:
        return None


def _save_offset(offset: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(str(offset))


def run() -> None:
    if not tg.is_configured():
        print("✗ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in engine/.env — aborting.")
        return

    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        job_generate_daily,
        CronTrigger(hour=PROMPT_HOUR, minute=PROMPT_MINUTE, timezone=TIMEZONE),
        id="generate_daily",
    )
    scheduler.start()
    print(f"Journey daemon started — generates daily at {PROMPT_HOUR:02d}:{PROMPT_MINUTE:02d} {TIMEZONE}")

    offset = _load_offset()
    try:
        while True:
            try:
                updates = tg.get_updates(offset=offset, timeout=30)
            except Exception as e:
                print(f"  ⚠ getUpdates failed: {e}")
                time.sleep(5)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                _save_offset(offset)
                try:
                    handle_update(u)
                except Exception as e:
                    print(f"  ⚠ handle_update failed: {e}")
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=False)
        stop_mpt()


if __name__ == "__main__":
    run()
