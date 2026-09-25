#!/usr/bin/env python3
"""
Telegram-driven Founder's Journey daemon — the automated version of:
  python main.py --journey-video --milestone "..."

Every day at 08:50 Europe/Athens the bot asks what you built today. Reply
in Telegram with a short milestone and it generates the journey video the
same way `--journey-video` does, then sends it back with Approve/Regenerate
buttons. Send any text before tapping Regenerate and it's used as a rewrite
note for the next take. Approve just marks the video done — posting is
still manual (dashboard or `main.py --post-social`), by design.

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
from core.prediction_fetcher import fetch_picks
from core.script_generator import ScriptQualityError, generate_journey_script, project_day
from core.video_builder import build_journey_video, stop_mpt

TIMEZONE = "Europe/Athens"
PROMPT_HOUR, PROMPT_MINUTE = 8, 50

STATE_PATH = Path(__file__).resolve().parent / "assets" / "output" / "journey_state.json"
OFFSET_PATH = Path(__file__).resolve().parent / "assets" / "output" / "telegram_offset.txt"


# ── State ──────────────────────────────────────────────────────────
# journey_state.json: {date, status, milestone, feedback, video_path,
#                       video_message_id, attempts}
# status: idle | awaiting_milestone | generating | awaiting_approval | error | approved

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

def _generate_and_send(state: dict) -> None:
    state["status"] = "generating"
    _save_state(state)

    milestone = state["milestone"]
    if state.get("feedback"):
        milestone = f"{milestone}\n\n(Revision note for this take: {state['feedback']})"

    tg.send_message("⚙️ Generating today's video, hang tight...")
    try:
        picks = fetch_picks(exclude_corners=True, top=3)
    except Exception as e:
        picks = []
        print(f"  ⚠ fetch_picks failed: {e}")

    try:
        script = generate_journey_script(picks, milestone=milestone)
    except ScriptQualityError as e:
        state["status"] = "error"
        state["attempts"] += 1
        _save_state(state)
        tg.send_message(
            f"✗ Script never cleared the quality gate after {e.revisions} rewrite(s) "
            f"(avg {e.scores['avg']}). Tap Regenerate to try again, or send a note first.",
            reply_markup=tg.RETRY_KEYBOARD,
        )
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


def job_prompt_milestone() -> None:
    """08:50 Athens — ask what today's milestone is, unless today's already handled."""
    state = _today_state()
    if state["status"] != "idle":
        return
    day = project_day()
    state["status"] = "awaiting_milestone"
    _save_state(state)
    tg.send_message(f"☀️ Day {day} — what did you build/work on today? Reply here to generate the video.")


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
        job_prompt_milestone,
        CronTrigger(hour=PROMPT_HOUR, minute=PROMPT_MINUTE, timezone=TIMEZONE),
        id="prompt_milestone",
    )
    scheduler.start()
    print(f"Journey daemon started — prompts daily at {PROMPT_HOUR:02d}:{PROMPT_MINUTE:02d} {TIMEZONE}")

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
