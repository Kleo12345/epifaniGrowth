"""Code gates on voiceovers and captions (script_generator._BANNED & co).

Run: cd engine && python -m pytest core/test_text_gates.py -q
"""
from core.prediction_fetcher import Pick
from core.script_generator import (_SITE_LINK, _fix_opener, _hard_problems, _safe_caption,
                                   _spoken_call)


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
    assert out["caption"].endswith("the model's calls are free at epifanii.com/register")
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


def test_site_cta_points_to_register_on_tiktok_youtube_x():
    tt = _safe_caption("tiktok", "hi", "", "site")["caption"]
    assert tt == "hi\nthe model's calls are free at epifanii.com/register"
    yt = _safe_caption("youtube", "Title\nDesc.", "", "site")["caption"]
    assert yt == "Title\nDesc.\nThe model's calls are free at https://epifanii.com/register"
    xx = _safe_caption("x", "hi", "", "site")["caption"]
    assert xx == "hi\nfree at epifanii.com/register"
    ig = _safe_caption("instagram", "hi", "", "site")["caption"]
    assert ig.endswith("epifanii.com (link in bio)") and "/register" not in ig


def test_bare_domain_is_rewritten_to_register_but_never_doubled():
    tt = _safe_caption("tiktok", "new day.\nfree at epifanii.com", "", "site")["caption"]
    assert tt == "new day.\nfree at epifanii.com/register"
    yt = _safe_caption("youtube", "Title\nSee https://epifanii.com.", "", "site")["caption"]
    assert yt == "Title\nSee https://epifanii.com/register."
    xx = _safe_caption("x", "free at www.epifanii.com/ now", "", "site")["caption"]
    assert xx == "free at www.epifanii.com/register now"
    done = _safe_caption("tiktok", "go to epifanii.com/register", "", "site")["caption"]
    assert done == "go to epifanii.com/register"


def test_comment_mode_youtube_and_x_links_go_to_register_instagram_untouched():
    yt = _safe_caption("youtube", "Title\nfree at epifanii.com", "", "comment")["caption"]
    assert yt.endswith("epifanii.com/register")
    ig = _safe_caption("instagram", "free at epifanii.com", "", "comment")["caption"]
    assert ig == "free at epifanii.com"


def _rewrite(text):
    return _SITE_LINK.sub(r"\g<1>epifanii.com/register", text)


def test_site_link_leaves_email_and_subdomain_alone():
    assert _rewrite("mail me: x@epifanii.com") == "mail me: x@epifanii.com"
    assert _rewrite("docs at sub.epifanii.com today") == "docs at sub.epifanii.com today"
    assert _rewrite("see www.sub.epifanii.com") == "see www.sub.epifanii.com"
    assert _rewrite("myepifanii.com") == "myepifanii.com"
    assert _rewrite("epifanii.com.au") == "epifanii.com.au"


def test_site_link_rewrites_bare_domain_including_before_punctuation():
    assert _rewrite("free at epifanii.com") == "free at epifanii.com/register"
    assert _rewrite("free at EPIFANII.COM now") == "free at epifanii.com/register now"
    assert _rewrite("go to https://epifanii.com/ now") == "go to https://epifanii.com/register now"
    assert _rewrite("see www.epifanii.com.") == "see www.epifanii.com/register."
    assert _rewrite("it is epifanii.com, free") == "it is epifanii.com/register, free"
    assert _rewrite("(epifanii.com)") == "(epifanii.com/register)"


def test_site_link_never_doubles_register_and_skips_paths_and_queries():
    for s in ("epifanii.com/register", "https://epifanii.com/register.",
              "epifanii.com/transparency", "epifanii.com/register?utm_source=tiktok",
              "epifanii.com/?utm_source=x", "epifanii.com?utm_source=x", "epifanii.com#top"):
        assert _rewrite(s) == s, s
    assert _rewrite(_rewrite("epifanii.com")) == "epifanii.com/register"


def test_safe_caption_does_not_treat_an_email_as_the_link():
    out = _safe_caption("tiktok", "mail x@epifanii.com", "", "site")["caption"]
    assert out.startswith("mail x@epifanii.com\n")
    assert out.endswith("free at epifanii.com/register")
