"""Code gates on voiceovers and captions (script_generator._BANNED & co).

Run: cd engine && python -m pytest core/test_text_gates.py -q
"""
from core.prediction_fetcher import Pick
from core.script_generator import _fix_opener, _hard_problems, _safe_caption, _spoken_call


def _pick(market, outcome):
    return Pick(match_id="1", league="Eliteserien", match="Bodo/Glimt vs Viking",
                home_team="Bodo/Glimt", away_team="Viking", time_str="18:00", market=market,
                outcome=outcome, odds=2.1, probability=0.81, edge=0.1, tier="HIGH CONFIDENCE",
                tier_color="#00f2ff", label="Draw No Bet: Away", confidence_pct=81)


def test_filler_openers_are_stripped():
    assert _fix_opener("Okay, so honestly, I wasted a week.") == "I wasted a week."
    assert _fix_opener("Honestly, the scariest part") == "The scariest part"
    assert _fix_opener("Okay so you know how") == "So you know how"
    # real first words survive
    assert _fix_opener("So many bugs today.") == "So many bugs today."
    assert _fix_opener("Okayish day.") == "Okayish day."


def test_hard_problems():
    assert _hard_problems("My pipeline broke while I slept. Then I fixed it.") == ""
    long_hook = _hard_problems("This new sharing method for the model is either genius or a mess.")
    assert "first sentence is 13 words" in long_hook
    assert "'bet'" in _hard_problems("Short hook. The engine called draw no bet away.")
    assert "'odds'" in _hard_problems("Short hook. At odds of two.")
    assert _hard_problems("Short hook. I bettered the model.") == ""  # word boundary


def test_spoken_call_has_no_betting_market_names():
    assert _spoken_call(_pick("DNB", "A")) == "Viking not to lose"
    assert _spoken_call(_pick("Result (1/X/2)", "H")) == "Bodo/Glimt to win"
    assert _spoken_call(_pick("Result (1/X/2)", "D")) == "a draw"


def test_day9_tiktok_caption_is_cleaned():
    cap = ("my football data nightmare for epifani finally ended. pipeline is automated.\n"
           "engine called bodo/glimt vs viking draw no bet away at 81% confidence.\n"
           "comment MODEL")
    out = _safe_caption("tiktok", cap, "#buildinpublic #ai #bettingtips #footballdata", "site")
    assert "bet" not in out["caption"].lower() and "81" not in out["caption"]
    assert out["caption"].endswith("the model's calls are free at epifanii.com")
    assert out["hashtags"] == "#buildinpublic #ai #footballdata"


def test_site_link_added_once_and_percent_allowed_off_tiktok():
    out = _safe_caption("instagram", "Model said 81% today.\nepifanii.com", "#ai", "site")
    assert out["caption"] == "Model said 81% today.\nepifanii.com"
    assert "epifanii.com" not in _safe_caption("tiktok", "hi", "", "comment")["caption"]


def test_youtube_keeps_a_title_when_every_line_is_dropped():
    out = _safe_caption("youtube", "Draw no bet madness", "", "site")
    assert out["caption"].splitlines()[0] == "Building an AI that predicts football"


def test_instagram_link_in_bio_counts_as_the_cta():
    out = _safe_caption("instagram", "See the record. Link in bio.", "", "site")
    assert out["caption"] == "See the record. Link in bio."
