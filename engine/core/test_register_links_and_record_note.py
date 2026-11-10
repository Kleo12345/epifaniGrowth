"""Tests for the G3 sign-up work: Pick.cta_url -> /register with a UTM, and record days
speaking their calendar note without ever taking a statistic from it.
No network, no Gemini: every model call is faked.

Run: cd engine && python -m pytest core/test_register_links_and_record_note.py -q
"""
import types

import pytest

from core import script_generator as sg
from core.prediction_fetcher import Pick

NOTE = ("End with a follow reason: tomorrow's video on how a model sizes its confidence. "
        "Ask one question viewers can answer in one word: hit rate or ROI?")
# A note that (wrongly) quotes figures. None of them may reach the prompt.
NOTE_WITH_FIGURES = (NOTE + " Last week was 937 picks at a 61.73% hit rate, ask 6173 viewers"
                     " and say 88 percent.")
PERF = {"windowDays": 30, "sample": 20, "hitRate": 0.7, "avgEdge": -0.041,
        "roi": -0.0729, "units": -1.5}


def _pick():
    return Pick(match_id="1", league="L", match="A vs B", home_team="A", away_team="B",
                time_str="18:00", market="DNB", outcome="A", odds=2.1, probability=0.8,
                edge=0.1, tier="HIGH CONFIDENCE", tier_color="#00f2ff", label="DNB: A",
                confidence_pct=80)


# ── Pick.cta_url ────────────────────────────────────────────────────

def test_cta_url_points_to_register_with_utm(monkeypatch):
    monkeypatch.delenv("UTM_SOURCE", raising=False)
    p = _pick()
    assert p.cta_url == "epifanii.com/register?utm_source=video&utm_medium=social"
    assert p.cta_link("x") == "epifanii.com/register?utm_source=x&utm_medium=social"
    monkeypatch.setenv("UTM_SOURCE", "tiktok")
    assert p.cta_url == "epifanii.com/register?utm_source=tiktok&utm_medium=social"


def test_image_card_text_is_the_bare_register_path(monkeypatch):
    monkeypatch.delenv("UTM_SOURCE", raising=False)
    # image_builder shows cta_url.split("?")[0].upper()
    assert _pick().cta_url.split("?")[0].upper() == "EPIFANII.COM/REGISTER"


def test_thread_prompt_carries_the_register_link_with_the_x_source(monkeypatch):
    monkeypatch.delenv("UTM_SOURCE", raising=False)
    seen = []
    monkeypatch.setattr(sg, "_get_client", lambda: object())

    def fake(client, model, contents, **kw):
        seen.append(contents)
        return types.SimpleNamespace(text="one---TWEET---two---TWEET---three")

    monkeypatch.setattr(sg, "call_gemini_with_retry", fake)
    sg.generate_thread(_pick())
    assert ("CTA URL: https://epifanii.com/register?utm_source=twitter&utm_medium=social"
            in seen[0])


# ── record day: calendar note reaches the prompt, numbers do not ────

def _run_record(monkeypatch, note):
    prompts = []
    monkeypatch.setattr(sg, "_get_client", lambda: object())

    def fake(client, model, contents, **kw):
        prompts.append(contents)
        return types.SimpleNamespace(
            text="===VOICEOVER===\nMy model keeps a public record. It got some wrong. "
                 "Check it yourself.\n===CAPTION===\nthe record\n===HASHTAGS===\n#ai #buildinpublic")

    monkeypatch.setattr(sg, "call_gemini_with_retry", fake)
    # fixed hook: with hook_style=None the writer picks a random one, which would make two prompts differ
    script = sg.generate_track_record_script(PERF, [], hook_style=sg.HOOK_STYLES[0], cta_mode="site",
                                             calendar_note=note)
    return script, prompts


def test_note_text_reaches_the_writer_prompt_and_the_critic(monkeypatch):
    script, prompts = _run_record(monkeypatch, NOTE)
    assert "tomorrow's video on how a model sizes its confidence" in prompts[0]
    assert "hit rate or ROI?" in prompts[0]
    assert "TODAY'S CALENDAR DIRECTION" in prompts[0]
    assert "tomorrow's video on how a model sizes its confidence" in prompts[1]  # critic topic
    assert script.voiceover  # the faked take went through the gates


def test_no_number_from_the_note_is_used_as_a_stat(monkeypatch):
    _, prompts = _run_record(monkeypatch, NOTE_WITH_FIGURES)
    writer, critic = prompts[0], prompts[1]
    for figure in ("937", "61.73", "6173", "88 percent"):
        assert figure not in writer, figure
        assert figure not in critic, figure
    assert "tomorrow's video on how a model sizes its confidence" in writer  # words survive
    assert "[figure removed]" in writer
    assert "never from this direction" in writer
    # the record block is exactly the live stats, nothing else
    start = writer.index("THE MODEL'S RECORD")
    section = writer[start:writer.index("HARD LIMIT")]
    assert sg._perf_stats_block(PERF) in section
    assert "TODAY'S CALENDAR DIRECTION" not in section


def test_no_note_means_prompt_unchanged(monkeypatch):
    _, with_none = _run_record(monkeypatch, None)
    _, with_blank = _run_record(monkeypatch, "   ")
    assert "CALENDAR DIRECTION" not in with_none[0]
    assert with_none[0] == with_blank[0]
    assert "allowed direction, not a statistic" not in with_none[1]


def test_clean_calendar_note_redacts_figures_only():
    assert sg._clean_calendar_note("a 93% and 12.5 and 3,000 b") == \
        "a [figure removed] and [figure removed] and [figure removed] b"
    assert sg._clean_calendar_note("in 2026. Then 5 viewers") == \
        "in [figure removed]. Then [figure removed] viewers"
    assert sg._clean_calendar_note(None) == ""
    assert sg._clean_calendar_note("  tomorrow:\n  sizing  ") == "tomorrow: sizing"


# ── journey_daemon passes the note on record days ───────────────────

class _FakeTG:
    APPROVE_KEYBOARD = {"k": "approve"}
    RETRY_KEYBOARD = {"k": "retry"}

    def __init__(self):
        self.messages, self.videos = [], []

    def send_message(self, text, reply_markup=None):
        self.messages.append(text)
        return {"message_id": 1}

    def send_video(self, path, caption, reply_markup=None):
        self.videos.append(caption)
        return {"message_id": 2}


def _daemon(monkeypatch, tmp_path, entry):
    jd = pytest.importorskip("journey_daemon")  # needs apscheduler/requests etc. installed
    monkeypatch.setattr(jd, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(jd, "tg", _FakeTG())
    monkeypatch.setattr(jd, "project_day", lambda: 21)
    monkeypatch.setattr(jd, "calendar_entry", lambda d: dict(entry, day=d))
    monkeypatch.setattr(jd, "fetch_performance", lambda: PERF)
    monkeypatch.setattr(jd, "fetch_recent_winners", lambda: [])
    monkeypatch.setattr(jd, "fetch_picks", lambda **kw: [])
    monkeypatch.setattr(jd, "platform_captions", lambda script: {"instagram": {"caption": "c", "hashtags": "#ai"}})
    monkeypatch.setattr(jd, "build_journey_video", lambda picks, script, fam=None: {"video_path": "/tmp/x.mp4"})
    return jd


def test_daemon_passes_todays_note_into_the_record_script(monkeypatch, tmp_path):
    entry = {"fam": "proof", "hook": "FLEX", "topic": "Weekly record check-in", "note": NOTE,
             "kind": "record", "secs": None}
    jd = _daemon(monkeypatch, tmp_path, entry)
    seen = {}

    def fake_track(perf, winners, hook_style=None, revision_note="", calendar_note=None):
        seen.update(perf=perf, note=calendar_note, revision=revision_note)
        return types.SimpleNamespace(day=21, caption="c", hashtags="#ai", voiceover="v",
                                     milestone="m")

    monkeypatch.setattr(jd, "generate_track_record_script", fake_track)
    jd.job_generate_daily()
    assert seen["note"] == NOTE
    assert seen["perf"] == PERF  # the stats come from fetch_performance, not from the note
    assert jd._load_state()["status"] == "awaiting_approval"


def test_daemon_record_day_without_a_note_passes_none(monkeypatch, tmp_path):
    entry = {"fam": "proof", "hook": "FLEX", "topic": "Weekly record check-in", "note": None,
             "kind": "record", "secs": None}
    jd = _daemon(monkeypatch, tmp_path, entry)
    seen = {}
    monkeypatch.setattr(jd, "generate_track_record_script",
                        lambda perf, winners, **kw: seen.update(kw) or types.SimpleNamespace(
                            day=21, caption="c", hashtags="#ai", voiceover="v", milestone="m"))
    jd.job_generate_daily()
    assert seen["calendar_note"] is None


def test_calendar_record_days_are_the_expected_ones():
    from core.content_calendar import calendar_entry
    for day in (21, 28, 35, 39, 43):
        assert calendar_entry(day)["kind"] == "record", day
