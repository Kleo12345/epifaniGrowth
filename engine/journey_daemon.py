#!/usr/bin/env python3
"""
Telegram-driven Founder's Journey daemon — fully automated against the Plan A+
content calendar (core/content_calendar.py, 44 days).

Every day at 08:50 Europe/Athens the daemon looks up today's calendar day
(core.script_generator.project_day), generates that day's video straight from
the calendar's topic/hook/family — no prompt, no waiting on a reply — and
sends it to Telegram with Approve/Regenerate buttons. If the PC was off or
asleep through that slot, it catches up and generates today's video as soon
as the daemon next starts, instead of silently waiting for tomorrow's slot.
Send any text before
tapping Regenerate and it's used as a rewrite note for the next take; tap
Regenerate with no text and it just takes another pass at the same topic.
Approve posts the video to every connected platform (core/social_publish.py:
Instagram, TikTok inbox draft, YouTube Shorts, X) and reports the links; any
platform that fails gets a "Retry failed platforms" button. Every night at
22:30 a growth report (core/daily_report.py — metrics + Claude's analysis) is
sent to the same chat. Once day 45 arrives (the calendar is
exhausted) it falls back to asking what you built, same as before.

Run with:
  conda activate epifani-growth
  python journey_daemon.py
Or install as a systemd --user unit — see epifani-journey.service.

Crash recovery: if generation dies (e.g. the PC woke with no network yet), the
day goes back to "idle" and a 15-minute retry job picks it up again — up to
MAX_CRASH_RETRIES times, then it parks in "error" with a Regenerate button so a
persistent fault can't burn ElevenLabs credits all day. A restart that finds a
stale "generating" state treats it the same way.
"""
import json
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import telegram_bot as tg
from core.daily_report import daily_report, retry_pending_analysis
from core.social_publish import configured_platforms, publish
from core.content_calendar import calendar_entry
from core.prediction_fetcher import fetch_picks, fetch_performance, fetch_recent_winners
from core.script_generator import (
    CONTENT_FRAME_BY_FAM,
    ScriptQualityError,
    generate_journey_script,
    generate_track_record_script,
    hook_style_for_calendar,
    platform_captions,
    project_day,
)
from core import won_tickets
from core.video_builder import build_journey_video, stop_mpt
from publishers.upload_post_publisher import post_instagram_story, refresh_instagram_token
from tools.push_social import push as push_social

TIMEZONE = "Europe/Athens"
PROMPT_HOUR, PROMPT_MINUTE = 8, 50
REPORT_HOUR, REPORT_MINUTE = 22, 30
TICKETS_HOUR, TICKETS_MINUTE = 8, 0  # after the epifani server grades last night's matches (~07:15 Athens)

STATE_PATH = Path(__file__).resolve().parent / "assets" / "output" / "journey_state.json"
OFFSET_PATH = Path(__file__).resolve().parent / "assets" / "output" / "telegram_offset.txt"
# tickets_state.json: {day, paths, posted, disclaimer_month} — see job_won_tickets
TICKETS_STATE_PATH = Path(__file__).resolve().parent / "assets" / "output" / "tickets_state.json"


# ── State ──────────────────────────────────────────────────────────
# journey_state.json: {date, status, milestone, feedback, video_path,
#                       video_message_id, attempts, calendar_day, fam, hook, kind,
#                       script: {day, milestone, voiceover, caption, hashtags},
#                       posted: {platform: url|None}}
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
        f"✗ Script never cleared the quality gate in {MAX_GATE_ATTEMPTS} fresh takes "
        f"(last avg {e.scores['avg']}). Tap Regenerate to try again, or send a note first.",
        reply_markup=tg.RETRY_KEYBOARD,
    )


MAX_GATE_ATTEMPTS = 6


def _until_gate_clears(generate):
    """Fresh takes until one clears the critic gate, so a near-miss (e.g. the
    condense pass knocking a floor axis) doesn't need a manual Regenerate.
    ponytail: capped at MAX_GATE_ATTEMPTS to bound Gemini spend on a topic that
    can never pass; only then is the founder asked."""
    for attempt in range(1, MAX_GATE_ATTEMPTS + 1):
        try:
            return generate()
        except ScriptQualityError as e:
            print(f"  ↻ Gate miss {attempt}/{MAX_GATE_ATTEMPTS} (avg {e.scores['avg']}) — fresh take")
            if attempt == MAX_GATE_ATTEMPTS:
                raise


MAX_CRASH_RETRIES = 3


def _recover_from_crash(state: dict, err: object) -> None:
    """Generation died mid-way: back to idle so the 15-min retry job tries again,
    or park in error after MAX_CRASH_RETRIES so a persistent fault stops retrying."""
    state["crashes"] = state.get("crashes", 0) + 1
    gave_up = state["crashes"] >= MAX_CRASH_RETRIES
    state["status"] = "error" if gave_up else "idle"
    _save_state(state)
    print(f"  ⚠ generation crashed ({err}) — "
          + ("giving up, waiting for Regenerate" if gave_up else "will retry in ≤15 min"))
    if gave_up:
        try:
            tg.send_message(f"✗ Today's video failed {state['crashes']} times ({err}). "
                            "Tap Regenerate to try again.", reply_markup=tg.RETRY_KEYBOARD)
        except Exception:
            pass  # still offline — the state is saved, Regenerate works once it's back


def _generate_and_send(state: dict) -> None:
    try:
        _build_and_send(state)
    except Exception as e:
        _recover_from_crash(state, e)


def _build_and_send(state: dict) -> None:
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
            script = _until_gate_clears(lambda: generate_track_record_script(
                perf, winners, hook_style=hook_style, revision_note=feedback or "",
            ))
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
            script = _until_gate_clears(lambda: generate_journey_script(
                picks, milestone=milestone, hook_style=hook_style,
                content_frame=CONTENT_FRAME_BY_FAM.get(state.get("fam")),
                target_secs=state.get("secs") or 35,
            ))
        except ScriptQualityError as e:
            _report_quality_failure(state, e)
            return

    result = build_journey_video(picks, script=script, fam=state.get("fam"))
    if not result.get("video_path"):
        state["status"] = "error"
        state["attempts"] += 1
        _save_state(state)
        tg.send_message(f"✗ Video build failed: {result.get('error')}", reply_markup=tg.RETRY_KEYBOARD)
        return

    state["video_path"] = str(result["video_path"])
    state["script"] = {k: getattr(script, k, "") for k in
                       ("day", "milestone", "voiceover", "caption", "hashtags")}
    state["captions"] = platform_captions(script)
    state["feedback"] = None
    state["attempts"] += 1
    state["status"] = "awaiting_approval"
    _save_state(state)

    caption = f"Day {script.day} — attempt {state['attempts']}\n\n{script.caption}"
    tg.send_message(_caption_preview(state["captions"]))
    msg = tg.send_video(result["video_path"], caption=caption, reply_markup=tg.APPROVE_KEYBOARD)
    state["video_message_id"] = msg["message_id"]
    _save_state(state)


def _caption_preview(captions: dict) -> str:
    """What Approve will post, per connected platform — reviewed before it goes live."""
    lines = ["📝 Captions that will be posted on Approve:"]
    for p in configured_platforms():
        c = captions.get(p) or {}
        lines.append(f"\n— {p.upper()} —\n{c.get('caption', '')}\n{c.get('hashtags', '')}")
    return "\n".join(lines)


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
    state["secs"] = entry.get("secs")
    state["milestone"] = milestone
    _save_state(state)
    _generate_and_send(state)


def _catch_up_if_missed() -> None:
    """Run on every startup: a cron trigger only fires while the process is
    alive, so if the PC was off/asleep through today's 08:50 slot, the
    schedule doesn't catch up on its own — it just waits for tomorrow. This
    generates today's video immediately instead, the same job the cron would
    have run, if that slot has already passed and nothing's been generated yet."""
    now = datetime.now(ZoneInfo(TIMEZONE))
    scheduled = now.replace(hour=PROMPT_HOUR, minute=PROMPT_MINUTE, second=0, microsecond=0)
    if now < scheduled:
        return  # today's slot hasn't arrived yet — the normal cron will fire it
    state = _today_state()
    if state["status"] != "idle":
        return  # already generated (or in progress/awaiting input) today
    print(f"  ⏰ Today's {PROMPT_HOUR:02d}:{PROMPT_MINUTE:02d} {TIMEZONE} video isn't made yet "
          f"(missed slot or earlier crash) — catching up now.")
    job_generate_daily()


# ── Posting + nightly report ───────────────────────────────────────

def _publish(state: dict) -> None:
    """Post the approved video to every connected platform not already posted to."""
    posted = state.setdefault("posted", {})
    todo = [p for p in configured_platforms() if p not in posted]
    if not todo:
        tg.send_message(f"✅ Approved — {state['video_path']}\n"
                        + ("Already posted everywhere." if posted else
                           "No social accounts connected yet — post it yourself."))
        return
    tg.send_message(f"📤 Posting to {', '.join(todo)}...")
    meta = {k: state.get(k) for k in ("kind", "fam", "hook")}
    results = publish(state["video_path"], state.get("script") or {}, meta, todo,
                      captions=state.get("captions"))

    lines, failed = [], []
    for p, r in results.items():
        if r["ok"]:
            posted[p] = r["url"]
            if p == "tiktok":
                lines.append(f"✅ tiktok: draft is in your TikTok inbox — open the app NOW, "
                             f"paste this caption, tap Post. Never post two days' drafts "
                             f"back to back: TikTok throttles reach on batched posts.\n{r['caption']}")
            else:
                lines.append(f"✅ {p}: {r['url'] or 'posted'}")
        else:
            failed.append(p)
            lines.append(f"✗ {p}: {r['error']}")
    _save_state(state)
    tg.send_message("\n\n".join(lines),
                    reply_markup=tg.RETRY_POST_KEYBOARD if failed else None)


def job_nightly_report() -> None:
    """22:30 Athens — keep the Instagram token alive, then send the growth report."""
    if os.getenv("INSTAGRAM_ACCESS_TOKEN"):
        try:
            refresh_instagram_token()
        except Exception as e:
            tg.send_message(f"⚠️ Instagram token refresh failed ({e}). If it has expired, "
                            "generate a new one in the Meta developer dashboard and put it in "
                            "INSTAGRAM_ACCESS_TOKEN in engine/.env.")
    try:
        tg.send_message(daily_report())
    except Exception as e:
        print(f"  ⚠ nightly report failed: {e}")
        tg.send_message(f"⚠️ Tonight's growth report failed: {e}")


def _tickets_state() -> dict:
    return json.loads(TICKETS_STATE_PATH.read_text()) if TICKETS_STATE_PATH.exists() else {}


def job_won_tickets() -> None:
    """08:00 Athens — yesterday's top-5 winning public picks as Story tickets, sent for approval.
    The first batch of each month opens with the highlight's disclaimer story."""
    day = (date.today() - timedelta(days=1)).isoformat()
    st = _tickets_state()
    if st.get("day") == day or st.get("recap_month") == day[:7]:
        return  # done, or that month's recap already covers it

    try:
        paths, n_picks, n_won = won_tickets.build_day(day)
    except Exception as e:
        tg.send_message(f"⚠️ Won tickets for {day} failed: {e}")
        return
    new_month = bool(paths) and st.get("disclaimer_month") != day[:7]
    if new_month:
        paths.insert(0, won_tickets.build_disclaimer(date.fromisoformat(day)))
    st.update(day=day, paths=[str(p) for p in paths], posted=[])
    TICKETS_STATE_PATH.write_text(json.dumps(st, indent=2))
    if not paths:
        tg.send_message(f"🎟 No winning public picks on {day} ({n_picks} settled) — no tickets today.")
        return
    tg.send_photos(paths, caption=f"🎟 Won tickets {day}: top {len(paths) - new_month} of {n_won}/{n_picks} calls")
    note = f"\nNew month: start a highlight 'Won tickets · {date.fromisoformat(day):%b %Y}' with the disclaimer first." if new_month else ""
    tg.send_message(f"Post these {len(paths)} as Instagram Stories?{note}", reply_markup=tg.POST_TICKETS_KEYBOARD)


def send_month_recap(month: str) -> None:
    """One-off, e.g. send_month_recap("2026-10"): the month's best singles and doubles for its
    highlight, behind the same Post button. Days of that month get no daily batch afterwards."""
    paths = won_tickets.build_recap(month)
    if not paths:
        tg.send_message(f"🎟 No winning public picks in {month}.")
        return
    first = date.fromisoformat(f"{month}-01")
    st = _tickets_state()
    if st.get("disclaimer_month") != month:
        paths.insert(0, won_tickets.build_disclaimer(first))
    st.update(day=f"{month}-recap", paths=[str(p) for p in paths], posted=[], recap_month=month)
    TICKETS_STATE_PATH.write_text(json.dumps(st, indent=2))
    tg.send_photos(paths, caption=f"🎟 {first:%B} recap: {len(paths)} stories")
    tg.send_message(f"Post these {len(paths)} as Instagram Stories? Then add them to the highlight "
                    f"'Won tickets · {first:%b %Y}', disclaimer first.", reply_markup=tg.POST_TICKETS_KEYBOARD)


def _post_tickets() -> None:
    """Post today's tickets that aren't up yet, in order; failures keep a retry button."""
    st = _tickets_state()
    if not st.get("paths"):
        return
    errors = []
    for p in st.get("paths", []):
        if p in st["posted"]:
            continue
        try:
            post_instagram_story(Path(p))
            st["posted"].append(p)
        except Exception as e:
            errors.append(f"{Path(p).name}: {e}")
            break  # keep the order: stop at the first failure, retry resumes here
    if any("disclaimer_" in p for p in st["posted"]):
        st["disclaimer_month"] = st["day"][:7]
    TICKETS_STATE_PATH.write_text(json.dumps(st, indent=2))
    msg = f"📤 {len(st['posted'])}/{len(st['paths'])} stories posted."
    if errors:
        tg.send_message(f"{msg}\n✗ {errors[0]}", reply_markup=tg.POST_TICKETS_KEYBOARD)
    else:
        tg.send_message(f"{msg} Add them to this month's highlight in the app.")


def job_push_social() -> None:
    """Every 30 min: channel views/followers to the Bot Dashboard's Social tab."""
    try:
        push_social()
    except Exception as e:
        print(f"  ⚠ social dashboard push failed: {e}")


def job_retry_analysis() -> None:
    """Hourly: if last night's report went out without Claude's analysis, try again."""
    try:
        msg = retry_pending_analysis()
        if msg:
            tg.send_message(msg)
    except Exception as e:
        print(f"  ⚠ analysis retry failed: {e}")


# ── Telegram event handling ────────────────────────────────────────

def handle_update(update: dict) -> None:
    if "callback_query" in update:
        cq = update["callback_query"]
        if str(cq["message"]["chat"]["id"]) != _own_chat_id():
            return
        tg.answer_callback(cq["id"])

        data = cq.get("data")
        if data == "post_tickets":  # independent of the video's daily state
            tg.edit_reply_markup(cq["message"]["message_id"])
            _post_tickets()
            return
        state = _today_state()
        if data == "retry_post" and state["status"] == "approved":
            tg.edit_reply_markup(cq["message"]["message_id"])
            _publish(state)
            return
        if state["status"] not in ("awaiting_approval", "error"):
            return

        if data == "approve":
            state["status"] = "approved"
            _save_state(state)
            tg.edit_reply_markup(cq["message"]["message_id"])
            _publish(state)
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
        # Default grace is 1s, so a PC asleep at 08:50 silently skipped the day. None =
        # run it whenever the machine wakes (the job itself no-ops if today's already done).
        misfire_grace_time=None,
    )
    scheduler.add_job(
        job_nightly_report,
        CronTrigger(hour=REPORT_HOUR, minute=REPORT_MINUTE, timezone=TIMEZONE),
        id="nightly_report",
        misfire_grace_time=None,
    )
    scheduler.add_job(
        job_won_tickets,
        CronTrigger(hour=TICKETS_HOUR, minute=TICKETS_MINUTE, timezone=TIMEZONE),
        id="won_tickets",
        misfire_grace_time=None,
    )
    # Retry net: re-runs the (idempotent) catch-up so a day that crashed back to idle,
    # or a wake from sleep the cron missed, gets generated without a restart.
    scheduler.add_job(_catch_up_if_missed, "interval", minutes=15, id="retry_catch_up")
    scheduler.add_job(job_retry_analysis, "interval", hours=1, id="retry_analysis")
    scheduler.add_job(job_push_social, "interval", minutes=30, id="push_social",
                      next_run_time=datetime.now(ZoneInfo(TIMEZONE)))  # first push right away
    scheduler.start()
    print(f"Journey daemon started — generates daily at {PROMPT_HOUR:02d}:{PROMPT_MINUTE:02d} {TIMEZONE}")
    state = _load_state()
    if state.get("status") == "generating":  # died mid-build last run
        _recover_from_crash(state, "daemon restarted mid-generation")
    threading.Thread(target=_catch_up_if_missed, daemon=True).start()

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
