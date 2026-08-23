"""
Epifani Growth Engine — Streamlit Dashboard

Launch with:
  conda activate epifani-growth
  cd engine
  streamlit run web_ui/dashboard.py
"""
import os
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.prediction_fetcher      import fetch_picks, MARKET_TABS, fetch_performance, fetch_recent_winners
from core.image_builder           import build_all_cards
from dataclasses                  import replace as _dc_replace
from core.script_generator        import (generate_all_threads, generate_journey_script,
                                          generate_track_record_script, platform_captions,
                                          project_day, JourneyScript, suggest_inserts,
                                          COMMENT_GATE_WORD)
from core.asset_loop              import character_assets
from core.visuals                 import load_library
from core.video_builder           import build_all_videos, build_journey_video, start_mpt
from core.analytics               import get_recent, weekly_summary, total_stats, set_result
from publishers.twitter_publisher import post_all_threads, is_configured as tw_configured
from publishers.upload_post_publisher import post_all_videos, is_configured as up_configured
from publishers.youtube_publisher import post_all_shorts, is_configured as yt_configured
from i18n                         import t, LANGS

_ENGINE_DIR = Path(__file__).resolve().parent.parent

# ── Scheduler helpers ─────────────────────────────────────────────
# scheduler_ctl spawns core/scheduler.py directly with sys.executable rather
# than shelling out to start_scheduler.sh, so this works the same on Windows
# (no bash) as on Linux/macOS.
from scheduler_ctl import get_pid as _scheduler_pid, start as _start_scheduler, stop as _stop_scheduler


# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Epifani Growth Engine",
    page_icon="⚽",
    layout="wide",
)

# Language selector runs first (top of sidebar) so every t() call below,
# including the title, already sees the chosen language.
with st.sidebar:
    _lang_display = st.selectbox(t("lang_label"), list(LANGS.keys()), key="lang_select")
    st.session_state["lang"] = LANGS[_lang_display]

st.markdown("""
<style>
  .main { background-color: #0a0a0c; }
  h1, h2, h3 { color: #00f2ff; }
  .stButton > button {
    background-color: #00f2ff22;
    border: 1px solid #00f2ff88;
    color: white;
    border-radius: 8px;
  }
  .stButton > button:hover {
    background-color: #00f2ff44;
    border-color: #00f2ff;
  }
  .tier-elite  { color: #00ff88; font-weight: bold; }
  .tier-high   { color: #00f2ff; font-weight: bold; }
  .tier-strong { color: #7000ff; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title(t("app_title"))
st.caption(t("app_caption", day=project_day()))


@st.cache_data(ttl=300)
def _load_picks(exclude_corners: bool, top_n: int, excluded_markets: frozenset, value_bets_only: bool):
    return fetch_picks(exclude_corners=exclude_corners, top=top_n, exclude_markets=excluded_markets, value_bets_only=value_bets_only)


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.header(t("settings_header"))
    top_n = st.slider(t("max_picks_label"), min_value=1, max_value=10, value=3)

    st.divider()
    st.header(t("platforms_header"))
    post_twitter   = st.toggle("Twitter / X",  value=True)
    post_tiktok    = st.toggle("TikTok",       value=True)
    post_instagram = st.toggle("Instagram",    value=True)
    post_youtube   = st.toggle("YouTube Shorts", value=True)

    st.divider()
    dry_run = st.toggle(t("dry_run_label"), value=True)
    if dry_run:
        st.info(t("dry_run_info"))

    st.divider()
    st.header(t("exclude_markets_header"))
    excluded_markets = set()
    for tab_name, market_key in MARKET_TABS.items():
        if not st.toggle(tab_name, value=(tab_name != "Corners"), key=f"mkt_{tab_name}"):
            excluded_markets.add(market_key)
    exclude_corners = "Corners (Dynamic Line)" in excluded_markets

    st.divider()
    st.header(t("filters_header"))
    value_only = st.toggle(t("value_only_label"), value=True, help=t("value_only_help"))

    st.divider()
    st.header(t("credentials_header"))
    st.caption(t("cred_ok", name="Twitter")     if tw_configured()             else t("cred_missing", name="Twitter"))
    st.caption(t("cred_ok", name="Upload-Post") if up_configured()             else t("cred_missing", name="Upload-Post"))
    st.caption(t("cred_ok", name="YouTube")     if yt_configured()             else t("cred_missing", name="YouTube"))
    st.caption(t("cred_ok", name="Gemini")      if os.getenv("GEMINI_API_KEY") else t("cred_missing", name="Gemini"))


    st.divider()
    st.header(t("scheduler_header"))
    sched_pid = _scheduler_pid()
    if sched_pid:
        st.success(t("scheduler_running", pid=sched_pid))
        if st.button(t("scheduler_stop_btn")):
            _stop_scheduler()
            st.rerun()
    else:
        st.warning(t("scheduler_not_running"))
        if st.button(t("scheduler_start_btn")):
            _start_scheduler()
            st.rerun()


# ── Load picks with all filters applied ──────────────────────────
picks = _load_picks(
    exclude_corners=exclude_corners,
    top_n=top_n,
    excluded_markets=frozenset(excluded_markets),
    value_bets_only=value_only,
)

# ── Picks table with per-pick exclusion ──────────────────────────
if st.button(t("refresh_picks_btn"), key="refresh_top"):
    st.cache_data.clear()
    st.rerun()

active_picks = []
if not picks:
    st.info(t("no_picks_info"))
else:
    st.subheader(t("picks_header", n=len(picks)))
    st.caption(t("picks_caption"))

    tier_colors = {
        "ELITE SIGNAL":    "tier-elite",
        "HIGH CONFIDENCE": "tier-high",
        "STRONG SIGNAL":   "tier-strong",
    }

    hcols = st.columns([0.4, 3, 2.2, 1, 1.2, 1, 2])
    hcols[0].markdown("**✓**")
    hcols[1].markdown(f"**{t('col_match')}**")
    hcols[2].markdown(f"**{t('col_pick')}**")
    hcols[3].markdown(f"**{t('col_odds')}**")
    hcols[4].markdown(f"**{t('col_confidence')}**")
    hcols[5].markdown(f"**{t('col_edge')}**")
    hcols[6].markdown(f"**{t('col_tier')}**")

    for p in picks:
        row = st.columns([0.4, 3, 2.2, 1, 1.2, 1, 2])
        included = row[0].checkbox(
            label="include",
            value=True,
            key=f"pick_{p.match_id}",
            label_visibility="collapsed",
        )
        style = "" if included else "opacity:0.35;"
        row[1].markdown(f'<span style="{style}">{p.match}</span>',      unsafe_allow_html=True)
        row[2].markdown(f'<span style="{style}">{p.label}</span>',      unsafe_allow_html=True)
        row[3].markdown(f'<span style="{style}">@ {p.odds:.2f}</span>', unsafe_allow_html=True)
        row[4].markdown(f'<span style="{style}">{p.confidence_pct}%</span>', unsafe_allow_html=True)
        row[5].markdown(f'<span style="{style}">+{round(p.edge * 100, 1)}%</span>', unsafe_allow_html=True)
        css = tier_colors.get(p.tier, "")
        row[6].markdown(f'<span style="{style}" class="{css}">{p.tier}</span>', unsafe_allow_html=True)

    # Active picks = those with checkbox ON
    active_picks = [p for p in picks if st.session_state.get(f"pick_{p.match_id}", True)]
    excluded_count = len(picks) - len(active_picks)
    if excluded_count:
        st.caption(t("excluded_caption", excluded=excluded_count, active=len(active_picks)))
    else:
        st.caption(t("all_selected_caption", n=len(active_picks)))

# ── Founder's Journey Highlight ───────────────────────────────────
st.subheader(t("journey_header", day=project_day()))
journey_text = st.text_area(
    t("journey_text_label"),
    value="",
    placeholder=t("journey_text_placeholder"),
    help=t("journey_text_help"),
)

# Readiness indicators — what the video will actually use
_avatar = character_assets()
if os.getenv("ELEVENLABS_API_KEY"):
    _voice_status = t("voice_elevenlabs")
elif os.getenv("GEMINI_API_KEY"):
    _voice_status = t("voice_edge_needs_key")
else:
    _voice_status = t("voice_edge")
if _avatar and _avatar["closed"].name.startswith("character"):
    _poses = "+".join(p for p in ("closed", "mid", "open", "smile", "blink") if p in _avatar)
    _char_status = t("avatar_yours", poses=_poses)
elif _avatar:
    _char_status = t("avatar_placeholder")
else:
    _char_status = t("avatar_none")
st.caption(f"{_voice_status}  ·  {_char_status}")

_cta_choice = st.radio(
    t("cta_label"),
    [t("cta_site"), t("cta_comment", word=COMMENT_GATE_WORD)],
    horizontal=True, key="cta_choice",
    help=t("cta_help"),
)
cta_mode = "comment" if _cta_choice == t("cta_comment", word=COMMENT_GATE_WORD) else "site"

jcol1, jcol2, jcol3 = st.columns([1, 1, 2])
with jcol1:
    gen_journey = st.button(t("gen_journey_btn"), width="stretch")
with jcol2:
    gen_track = st.button(t("gen_track_btn"), width="stretch")
with jcol3:
    st.caption(t("journey_vs_track_caption"))

if gen_journey:
    if not journey_text.strip():
        st.warning(t("warn_write_milestone"))
    else:
        with st.spinner(t("spinner_writing")):
            try:
                js = generate_journey_script(active_picks, milestone=journey_text,
                                             cta_mode=cta_mode)
                st.session_state["journey_script"] = js
                st.session_state["journey_cta_mode"] = cta_mode
                # seed the editable fields with the fresh AI draft
                st.session_state["edit_voiceover"] = js.voiceover
                st.session_state["edit_caption"]   = js.caption
                st.session_state["edit_hashtags"]  = js.hashtags
                st.session_state.pop("platform_caps", None)
            except Exception as e:
                st.error(t("err_journey_failed", e=e))

if gen_track:
    with st.spinner(t("spinner_track")):
        try:
            _perf = fetch_performance()
            if not _perf or not _perf.get("sample"):
                st.warning(t("warn_no_perf"))
            else:
                js = generate_track_record_script(_perf, fetch_recent_winners(),
                                                  cta_mode=cta_mode)
                st.session_state["journey_script"] = js
                st.session_state["journey_cta_mode"] = cta_mode
                st.session_state["edit_voiceover"] = js.voiceover
                st.session_state["edit_caption"]   = js.caption
                st.session_state["edit_hashtags"]  = js.hashtags
                st.session_state.pop("platform_caps", None)
                _hr = _perf.get("hitRate")
                st.success(t("success_track", hr=round((_hr or 0) * 100), sample=_perf.get("sample")))
        except Exception as e:
            st.error(t("err_track_failed", e=e))

if "journey_script" in st.session_state:
    js = st.session_state["journey_script"]
    mcol1, mcol2, mcol3 = st.columns(3)
    mcol1.metric(t("critic_score_label"), f"{js.critic_score}/10")
    mcol2.metric(t("rewrites_label"), js.revisions)
    mcol3.metric(t("est_length_label"), f"~{js.est_seconds}s")
    if js.critic_notes:
        st.caption(t("critic_notes_prefix", notes=js.critic_notes))

    st.caption(t("edit_script_caption"))
    st.text_area(t("voiceover_label"), key="edit_voiceover", height=160)
    st.text_area(t("caption_label"), key="edit_caption", height=70)
    st.text_area(t("hashtags_label"), key="edit_hashtags", height=50)

    # ── Per-platform caption variants ─────────────────────────────
    with st.expander(t("platform_captions_expander")):
        st.caption(t("platform_captions_caption"))
        if st.button(t("gen_platform_captions_btn")):
            _cap_src = _dc_replace(
                js,
                voiceover=st.session_state["edit_voiceover"].strip(),
                caption=st.session_state["edit_caption"].strip(),
                hashtags=st.session_state["edit_hashtags"].strip(),
            )
            with st.spinner(t("spinner_platform_captions")):
                try:
                    st.session_state["platform_caps"] = platform_captions(
                        _cap_src, cta_mode=st.session_state.get("journey_cta_mode", "site"))
                except Exception as e:
                    st.error(t("err_platform_captions", e=e))
        _caps = st.session_state.get("platform_caps")
        if _caps:
            for _p, _label in [("tiktok", "TikTok"), ("instagram", "Instagram"),
                               ("youtube", "YouTube"), ("x", "X")]:
                _v = _caps.get(_p, {})
                _body = (_v.get("caption", "").strip() + "\n\n" + _v.get("hashtags", "").strip()).strip()
                st.text_area(_label, value=_body, key=f"cap_{_p}", height=90)

    # ── Visual inserts (b-roll: code cards / screenshots shown while he talks) ──
    st.markdown(t("visual_inserts_header"))
    st.session_state.setdefault("insert_ids", [])
    st.session_state.setdefault("insert_seq", 0)
    _lib_ids = list(load_library().keys())

    for iid in list(st.session_state["insert_ids"]):
        with st.expander(t("insert_expander_title", iid=iid), expanded=True):
            _hint = st.session_state.get(f"ins_{iid}_hint")
            if _hint:
                st.caption(t("insert_ai_hint", hint=_hint))
            typ = st.radio(t("insert_type_label"), [t("insert_type_code"), t("insert_type_image")],
                           key=f"ins_{iid}_type", horizontal=True)
            if typ == t("insert_type_code"):
                st.text_area(t("insert_code_label"), key=f"ins_{iid}_code",
                             height=120, placeholder="def project_day(start=None):\n    ...")
                c1, c2 = st.columns(2)
                c1.text_input(t("insert_title_label"), key=f"ins_{iid}_title",
                              placeholder="script_generator.py")
                c2.text_input(t("insert_lang_label"), key=f"ins_{iid}_lang", value="python")
            else:
                if _lib_ids:
                    st.selectbox(t("insert_type_image"), _lib_ids, key=f"ins_{iid}_image")
                else:
                    st.text_input(t("insert_image_text_label"), key=f"ins_{iid}_image",
                                  placeholder="screenshots/dashboard.png")
            a1, a2, a3 = st.columns([3, 1, 1])
            a1.text_input(t("insert_at_label"), key=f"ins_{iid}_at",
                          placeholder=t("insert_at_placeholder"))
            a2.number_input(t("insert_secs_label"), key=f"ins_{iid}_secs", min_value=1.0,
                            max_value=15.0, value=3.0, step=0.5)
            if a3.button(t("insert_remove_btn"), key=f"ins_{iid}_rm"):
                st.session_state["insert_ids"].remove(iid)
                st.rerun()

    icol1, icol2 = st.columns([1, 2])
    if icol1.button(t("add_insert_btn")):
        st.session_state["insert_seq"] += 1
        st.session_state["insert_ids"].append(st.session_state["insert_seq"])
        st.rerun()
    if icol2.button(t("suggest_inserts_btn"), help=t("suggest_inserts_help")):
        with st.spinner(t("spinner_suggest")):
            try:
                cues = suggest_inserts(st.session_state.get("edit_voiceover", ""))
            except Exception as e:
                cues = []
                st.error(t("err_suggest_failed", e=e))
        if not cues:
            st.info(t("info_no_suggestions"))
        for c in cues:
            st.session_state["insert_seq"] += 1
            iid = st.session_state["insert_seq"]
            st.session_state["insert_ids"].append(iid)
            is_code = c["kind"] == "code"
            st.session_state[f"ins_{iid}_type"] = t("insert_type_code") if is_code else t("insert_type_image")
            st.session_state[f"ins_{iid}_at"]   = c["phrase"]
            st.session_state[f"ins_{iid}_secs"] = max(1.0, min(15.0, float(c.get("secs", 3.0))))
            st.session_state[f"ins_{iid}_hint"] = (
                c.get("what") or "") + (f"  (suggested: {c['kind']})" if c.get("kind") else "")
            if is_code:
                st.session_state[f"ins_{iid}_lang"] = "python"
        if cues:
            st.success(t("success_inserts_added", n=len(cues)))
        st.rerun()

    def _collect_inserts() -> list[dict]:
        out = []
        for iid in st.session_state.get("insert_ids", []):
            at_raw = (st.session_state.get(f"ins_{iid}_at") or "").strip()
            if not at_raw:
                continue
            try:
                at = float(at_raw)            # numeric → seconds
            except ValueError:
                at = at_raw                   # else → spoken phrase
            secs = float(st.session_state.get(f"ins_{iid}_secs", 3.0))
            if st.session_state.get(f"ins_{iid}_type") == t("insert_type_code"):
                code = (st.session_state.get(f"ins_{iid}_code") or "").strip()
                if not code:
                    continue
                out.append({"code": code,
                            "lang": (st.session_state.get(f"ins_{iid}_lang") or "python").strip(),
                            "title": (st.session_state.get(f"ins_{iid}_title") or "").strip() or None,
                            "at": at, "secs": secs})
            else:
                img = (st.session_state.get(f"ins_{iid}_image") or "").strip()
                if not img:
                    continue
                out.append({"image": img, "at": at, "secs": secs})
        return out

    if st.button(t("build_journey_video_btn"), type="primary"):
        edited = _dc_replace(
            js,
            voiceover=st.session_state["edit_voiceover"].strip(),
            caption=st.session_state["edit_caption"].strip(),
            hashtags=st.session_state["edit_hashtags"].strip(),
        )
        _inserts = _collect_inserts()
        if _inserts:
            st.caption(t("inserts_added_caption", n=len(_inserts)))
        with st.spinner(t("spinner_render")):
            try:
                result = build_journey_video(active_picks, script=edited, inserts=_inserts)
            except Exception as e:
                result = {"video_path": None, "error": str(e)}
        if result.get("video_path"):
            st.session_state["journey_video"] = str(result["video_path"])
            st.success(t("success_video_ready", path=result["video_path"]))
        else:
            st.error(t("err_video_build", error=result.get("error")))

    if "journey_video" in st.session_state and Path(st.session_state["journey_video"]).exists():
        st.video(st.session_state["journey_video"])

st.divider()

# ── Run full pipeline ─────────────────────────────────────────────
st.subheader(t("pipeline_header"))
st.caption(t("pipeline_caption"))

run_col1, run_col2 = st.columns([1, 3])
with run_col1:
    run_all = st.button(t("publish_btn"), type="primary", width="stretch")
with run_col2:
    if not active_picks:
        st.warning(t("warn_no_picks_selected"))
    elif dry_run:
        st.info(t("info_dry_run_pipeline"))
    else:
        platforms_active = [p for p, on in [("Twitter", post_twitter), ("TikTok", post_tiktok), ("Instagram", post_instagram), ("YouTube", post_youtube)] if on]
        st.caption(t("will_post_caption", n=len(active_picks),
                     platforms=", ".join(platforms_active) if platforms_active else t("no_platforms")))

if run_all:
    if not active_picks:
        st.error(t("err_no_picks_checked"))
    else:
        progress = st.progress(0, text=t("progress_start"))
        try:
            progress.progress(10, text=t("progress_cards"))
            cards = build_all_cards(active_picks)
            st.session_state["cards"] = cards

            progress.progress(25, text=t("progress_threads"))
            threads = generate_all_threads(active_picks, story_highlight=journey_text)
            st.session_state["threads"] = threads

            if post_tiktok or post_instagram or post_youtube:
                progress.progress(45, text=t("progress_videos"))
                start_mpt()
                video_results = build_all_videos(active_picks, story_highlight=journey_text)
                st.session_state["video_results"] = video_results
            else:
                video_results = []

            if post_twitter:
                progress.progress(70, text=t("progress_twitter"))
                pairs = [
                    {"thread": t2, "square": c["square"], "story": c["story"]}
                    for t2, c in zip(threads, cards)
                ]
                tw_results = post_all_threads(pairs, dry_run=dry_run)
                tw_ok = [r for r in tw_results if r["success"]]
                st.success(t("success_twitter", ok=len(tw_ok), total=len(active_picks)))

            if (post_tiktok or post_instagram) and video_results:
                progress.progress(85, text=t("progress_social"))
                items = [
                    {
                        "video_path": v["video_path"],
                        "caption": (
                            f"{v['pick'].match} — {v['pick'].label} @ {v['pick'].odds} | "
                            f"{v['pick'].confidence_pct}% AI Confidence\n"
                            f"epifanii.com/?ref=tiktok #football #AI"
                        ),
                        "match": v["pick"].match,
                    }
                    for v in video_results if v.get("video_path")
                ]
                if items:
                    social_results = post_all_videos(items, dry_run=dry_run)
                    social_ok = [r for r in social_results if r.get("success")]
                    st.success(t("success_social", ok=len(social_ok), total=len(items)))

            if post_youtube and video_results:
                progress.progress(95, text=t("progress_youtube"))
                items = [
                    {
                        "video_path": v["video_path"],
                        "caption": (
                            f"{v['pick'].match} — {v['pick'].label} @ {v['pick'].odds} | "
                            f"{v['pick'].confidence_pct}% AI Confidence\n"
                            f"epifanii.com/?ref=youtube #football #AI"
                        ),
                        "match": v["pick"].match,
                    }
                    for v in video_results if v.get("video_path")
                ]
                if items:
                    yt_results = post_all_shorts(items, dry_run=dry_run)
                    yt_ok = [r for r in yt_results if r.get("success")]
                    st.success(t("success_youtube", ok=len(yt_ok), total=len(items)))

            progress.progress(100, text=t("progress_done"))
            st.balloons()


        except Exception as e:
            st.error(t("err_pipeline_failed", e=e))
            progress.empty()

st.divider()

# ── Advanced: manual step-by-step controls ─────────────────────────
# Everything below duplicates what "🚀 Publish Today's Picks" already does
# in one click — kept for re-running a single step (e.g. re-post just the
# videos) without regenerating everything.
with st.expander(t("advanced_title")):
    st.caption(t("advanced_caption"))

    # ── Card preview ─────────────────────────────────────────────
    st.markdown(f"**{t('card_preview_header')}**")

    if st.button(t("generate_cards_btn"), key="adv_generate_cards"):
        with st.spinner(t("progress_cards")):
            cards = build_all_cards(active_picks)
        st.session_state["cards"] = cards
        st.success(t("success_cards_built", n=len(cards)))

    if "cards" in st.session_state:
        cols = st.columns(min(len(st.session_state["cards"]), 3))
        for i, card_data in enumerate(st.session_state["cards"]):
            with cols[i % 3]:
                st.image(str(card_data["square"]), caption=card_data["pick"].match, width="stretch")

    st.divider()

    # ── Tweet thread preview ────────────────────────────────────
    st.markdown(f"**{t('thread_preview_header')}**")

    if st.button(t("generate_threads_btn"), key="adv_generate_threads"):
        with st.spinner(t("spinner_gemini")):
            try:
                threads = generate_all_threads(active_picks)
                st.session_state["threads"] = threads
            except Exception as e:
                st.error(t("err_gemini_failed", e=e))

    if "threads" in st.session_state:
        for thread in st.session_state["threads"]:
            with st.expander(f"📋 {thread.pick.match}"):
                st.markdown(t("thread_tweet1", text=thread.tweet1))
                st.markdown(t("thread_tweet2", text=thread.tweet2))
                st.markdown(t("thread_tweet3", text=thread.tweet3))

    st.divider()

    # ── Video build ──────────────────────────────────────────────
    st.markdown(f"**{t('video_build_header')}**")

    if st.button(t("build_videos_btn"), key="adv_build_videos"):
        with st.spinner(t("spinner_build_videos")):
            try:
                start_mpt()
                video_results = build_all_videos(active_picks)
                st.session_state["video_results"] = video_results
                ok  = [v for v in video_results if v.get("video_path")]
                bad = [v for v in video_results if not v.get("video_path")]
                if ok:
                    st.success(t("success_videos_built", n=len(ok)))
                for v in bad:
                    st.error(f"{v['pick'].match}: {v.get('error', 'unknown error')}")
            except Exception as e:
                st.error(t("err_video_build_full", e=e))

    if "video_results" in st.session_state:
        ok_videos = [v for v in st.session_state["video_results"] if v.get("video_path")]
        if ok_videos:
            st.caption(t("videos_ready_caption", n=len(ok_videos),
                        matches=", ".join(v["pick"].match for v in ok_videos)))

    st.divider()

    # ── Publish controls ────────────────────────────────────────
    st.markdown(f"**{t('publish_header')}**")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(t("post_twitter_btn"), disabled=not post_twitter, key="adv_post_twitter"):
            if "cards" not in st.session_state:
                st.warning(t("warn_gen_cards_first"))
            elif "threads" not in st.session_state:
                st.warning(t("warn_gen_threads_first"))
            else:
                pairs = [
                    {"thread": th, "square": c["square"], "story": c["story"]}
                    for th, c in zip(st.session_state["threads"], st.session_state["cards"])
                ]
                with st.spinner(t("spinner_posting")):
                    results = post_all_threads(pairs, dry_run=dry_run)
                ok  = [r for r in results if r["success"]]
                bad = [r for r in results if not r["success"]]
                if ok:
                    st.success(t("success_threads_posted", n=len(ok)))
                for r in bad:
                    st.error(f"{r['match']}: {r.get('error')}")

    with col2:
        if st.button(t("post_social_btn"), disabled=not (post_tiktok or post_instagram), key="adv_post_social"):
            if not up_configured() and not dry_run:
                st.error(t("err_upload_post_not_configured"))
            else:
                video_dir = _ENGINE_DIR / "assets" / "output" / "videos"
                session_videos = {
                    v["pick"].match: v["video_path"]
                    for v in st.session_state.get("video_results", [])
                    if v.get("video_path")
                }
                items = []
                for p in active_picks:
                    vpath = session_videos.get(p.match)
                    if vpath is None:
                        safe = p.match.replace(" ", "_").replace("/", "-")
                        disk_path = video_dir / f"{safe}_branded.mp4"
                        vpath = disk_path if disk_path.exists() else None
                    if vpath:
                        items.append({
                            "video_path": vpath,
                            "caption": (
                                f"{p.match} — {p.label} @ {p.odds} | "
                                f"{p.confidence_pct}% AI Confidence\n"
                                f"epifanii.com/?ref=tiktok #football #AI"
                            ),
                            "match": p.match,
                        })
                    else:
                        st.warning(t("warn_no_video_for", match=p.match))

                if items:
                    with st.spinner(t("spinner_posting")):
                        results = post_all_videos(items, dry_run=dry_run)
                    ok = [r for r in results if r.get("success")]
                    st.success(t("success_social_uploaded", ok=len(ok), n=len(items)))

    with col3:
        if st.button(t("post_youtube_btn"), disabled=not post_youtube, key="adv_post_youtube"):
            if not yt_configured() and not dry_run:
                st.error(t("err_youtube_not_configured"))
            else:
                video_dir = _ENGINE_DIR / "assets" / "output" / "videos"
                session_videos = {
                    v["pick"].match: v["video_path"]
                    for v in st.session_state.get("video_results", [])
                    if v.get("video_path")
                }
                items = []
                for p in active_picks:
                    vpath = session_videos.get(p.match)
                    if vpath is None:
                        safe = p.match.replace(" ", "_").replace("/", "-")
                        disk_path = video_dir / f"{safe}_branded.mp4"
                        vpath = disk_path if disk_path.exists() else None
                    if vpath:
                        items.append({
                            "video_path": vpath,
                            "caption": (
                                f"{p.match} — {p.label} @ {p.odds} | "
                                f"{p.confidence_pct}% AI Confidence\n"
                                f"epifanii.com/?ref=youtube #football #AI"
                            ),
                            "match": p.match,
                        })
                    else:
                        st.warning(t("warn_no_video_for", match=p.match))

                if items:
                    with st.spinner(t("spinner_youtube_upload")):
                        results = post_all_shorts(items, dry_run=dry_run)
                    ok = [r for r in results if r.get("success")]
                    st.success(t("success_youtube_uploaded", ok=len(ok), n=len(items)))


# ── Analytics ────────────────────────────────────────────────────
st.divider()
st.subheader(t("analytics_header"))

totals = total_stats()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(t("metric_total_posted"), totals["total_posted"]    or 0)
m2.metric(t("metric_days_active"),  totals["days_active"]     or 0)
m3.metric(t("metric_wins"),         totals["total_wins"]      or 0)
m4.metric(t("metric_losses"),       totals["total_losses"]    or 0)
m5.metric(t("metric_avg_conf"),     f"{totals['avg_confidence'] or 0}%")

st.markdown(t("last_7_days"))
summary = weekly_summary()
if summary:
    import pandas as pd
    df = pd.DataFrame(summary)
    df.columns = t("weekly_cols").split(",")
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.caption(t("no_posts_logged"))

with st.expander(t("recent_posts_expander")):
    recent = get_recent(30)
    if recent:
        import pandas as pd
        df2 = pd.DataFrame(recent)[["date", "platform", "match", "label", "odds", "confidence_pct", "edge_pct", "result"]]
        df2.columns = t("recent_cols").split(",")
        st.dataframe(df2, width="stretch", hide_index=True)
    else:
        st.caption(t("nothing_yet"))

st.markdown(t("log_result_header"))
with st.form("log_result_form"):
    recent_unresolved = [r for r in get_recent(14) if not r.get("result")]
    match_options = sorted({f"{r['date']} — {r['match']}" for r in recent_unresolved})
    if match_options:
        selected = st.selectbox(t("pick_to_update_label"), match_options)
        _result_values = ["win", "loss", "void"]
        _result_display = {"win": t("result_win"), "loss": t("result_loss"), "void": t("result_void")}
        outcome = st.radio(t("result_label"), _result_values, format_func=lambda v: _result_display[v], horizontal=True)
        if st.form_submit_button(t("save_result_btn")):
            date_part, match_part = selected.split(" — ", 1)
            set_result(match_part, date_part, outcome)
            st.success(t("success_result_saved", match=match_part, outcome=_result_display[outcome]))
            st.rerun()
    else:
        st.caption(t("no_unresolved_caption"))
        st.form_submit_button(t("save_result_btn"), disabled=True)


# ── Status footer ─────────────────────────────────────────────────
st.divider()
sched_status = t("scheduler_running", pid=_scheduler_pid()) if _scheduler_pid() else t("footer_stopped")
st.caption(t("footer_text", status=sched_status, n=top_n))
