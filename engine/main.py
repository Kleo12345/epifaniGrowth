#!/usr/bin/env python3
"""
Epifani Growth Engine — CLI entry point

Usage:
  python main.py --list-picks                         # Show today's picks
  python main.py --generate-cards                     # Build image cards
  python main.py --build-videos                       # Build branded videos (needs MPT)
  python main.py --post-twitter                       # Post tweet threads
  python main.py --post-social                        # Post videos to TikTok + Instagram
  python main.py --run-all                            # Full pipeline
  python main.py --dry-run --run-all                  # Preview without posting
  python main.py --no-corners --top 3 --run-all       # Top 3, no corners
"""
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from core.prediction_fetcher          import fetch_picks
from core.image_builder               import build_all_cards
from core.script_generator            import (generate_all_threads, generate_journey_script,
                                               project_day, ScriptQualityError)
from core.video_builder               import build_all_videos, build_journey_video, stop_mpt
from core.analytics                   import log_post, get_today, get_recent, weekly_summary, total_stats, set_result
from publishers.twitter_publisher     import post_all_threads
from publishers.upload_post_publisher import post_all_videos
from publishers.youtube_publisher     import post_all_shorts


def _picks(args):
    return fetch_picks(
        exclude_corners = args.no_corners,
        top             = args.top,
    )


def _caption(pick) -> str:
    return (
        f"{pick.match} — {pick.label} @ {pick.odds} | "
        f"{pick.confidence_pct}% AI Confidence\n\n"
        f"Get all picks free → epifanii.com/?ref=tiktok #football #betting #AI"
    )


def cmd_list_picks(args):
    print("\n📡 Fetching predictions from Epifani...\n")
    picks = _picks(args)
    if not picks:
        print("  No qualifying picks found today.")
        return
    for p in picks:
        print(f"  ⚽ {p.match}")
        print(f"     {p.label} @ {p.odds}  |  {p.confidence_pct}%  |  {p.tier}")
        print()


def cmd_generate_cards(args):
    print("\n📡 Fetching predictions...\n")
    picks = _picks(args)
    if not picks:
        print("  No qualifying picks found.")
        return []
    print(f"  Found {len(picks)} qualifying pick(s). Building cards...\n")
    return build_all_cards(picks)


def cmd_journey_script(args):
    """Generate and print a Founder's Journey voiceover script for review."""
    if not args.milestone:
        print("Usage: --journey-script --milestone \"what you built today\"")
        print("  e.g. --journey-script --milestone 'Spent all night debugging the Portuguese league parser'")
        return

    print(f"\n📡 Fetching predictions for Day {project_day()} of building Epifani...\n")
    picks = _picks(args)
    if not picks:
        print("  No qualifying picks found today (script will reference the journey only).")

    print("✍️  Writing the journey script (Gemini writer → critic → rewriter)...\n")
    try:
        script = generate_journey_script(picks, milestone=args.milestone, cta_mode=args.cta)
    except ScriptQualityError as e:
        print(f"\n✗ Script blocked — never cleared the quality gate: {e}")
        return

    print("═" * 60)
    print(f"  DAY {script.day} — FOUNDER'S JOURNEY SCRIPT")
    print("═" * 60)
    print(f"\n  Milestone : {script.milestone}")
    print(f"  Critic    : {script.critic_score}/10  ({script.revisions} rewrite(s))")
    if script.critic_notes:
        print(f"  Notes     : {script.critic_notes}")
    print(f"  Length    : ~{script.est_seconds}s  ({script.word_count} words)")
    if script.picks:
        print("  Proof     : " + "; ".join(f"{p.match} ({p.label})" for p in script.picks))

    print("\n── VOICEOVER ───────────────────────────────────────────────\n")
    print(script.voiceover)
    print("\n── CAPTION ─────────────────────────────────────────────────\n")
    print(script.caption)
    print("\n── HASHTAGS ────────────────────────────────────────────────\n")
    print(script.hashtags)
    print()


def cmd_journey_video(args):
    """Generate the journey script AND build the branded journey video."""
    if not args.milestone:
        print("Usage: --journey-video --milestone \"what you built today\"")
        return

    print(f"\n📡 Fetching predictions for Day {project_day()} of building Epifani...\n")
    picks = _picks(args)
    if not picks:
        print("  No qualifying picks today — video will reference the journey only.")

    print("✍️  Writing the journey script (Gemini writer → critic → rewriter)...\n")
    try:
        script = generate_journey_script(picks, milestone=args.milestone, cta_mode=args.cta)
    except ScriptQualityError as e:
        print(f"\n✗ Video not built — script never cleared the quality gate: {e}")
        return
    print(f"  ✓ Day {script.day} script ready — critic {script.critic_score}/10, "
          f"~{script.est_seconds}s\n")

    print("🎬 Building the branded video (Asset Loop: local clips + Edge-TTS)...\n")
    result = build_journey_video(picks, script=script)

    if result.get("video_path"):
        print(f"\n✓ Journey video ready: {result['video_path']}")
        print(f"\n  Caption : {script.caption}")
        print(f"  Tags    : {script.hashtags}")
    else:
        print(f"\n✗ Video build failed: {result.get('error')}")


def cmd_build_videos(args):
    print("\n🎬 Building videos via MoneyPrinterTurbo...\n")
    picks = _picks(args)
    if not picks:
        print("  No qualifying picks found.")
        return []
    return build_all_videos(picks)


def cmd_post_twitter(args, cards=None, picks=None):
    if picks is None:
        print("\n📡 Fetching predictions...\n")
        picks = _picks(args)
    if not picks:
        print("  No qualifying picks found.")
        return

    if cards is None:
        print("  Building cards...\n")
        cards = build_all_cards(picks)

    print("\n✍️  Generating tweet threads via Gemini...\n")
    threads = generate_all_threads(picks)

    pairs = [
        {"thread": t, "square": c["square"], "story": c["story"]}
        for t, c in zip(threads, cards)
    ]

    label = "DRY RUN — " if args.dry_run else ""
    print(f"\n🐦 {label}Posting to Twitter/X...\n")
    results = post_all_threads(pairs, dry_run=args.dry_run)

    ok  = [r for r in results if r["success"]]
    bad = [r for r in results if not r["success"]]
    print(f"\n── Twitter Summary ─────────────────────────")
    print(f"  Posted:  {len(ok)}")
    print(f"  Failed:  {len(bad)}")
    for r in bad:
        print(f"  ✗ {r['match']}: {r.get('error')}")

    if not args.dry_run:
        pick_map = {p.match: p for p in picks}
        for r in ok:
            pick = pick_map.get(r["match"])
            if pick:
                post_id = r["urls"][0].split("/")[-1] if r.get("urls") else None
                log_post(pick, "twitter", post_id)


def cmd_post_social(args, video_results=None):
    print("\n📡 Fetching predictions...\n")
    picks = _picks(args)
    if not picks:
        print("  No qualifying picks found.")
        return

    if video_results is None:
        video_results = build_all_videos(picks)

    items = [
        {"video_path": v["video_path"], "caption": _caption(v["pick"]), "match": v["pick"].match}
        for v in video_results if v.get("video_path")
    ]

    if not items:
        print("  No videos available to post.")
        return

    label = "DRY RUN — " if args.dry_run else ""
    print(f"\n📲 {label}Posting to TikTok + Instagram...\n")
    results = post_all_videos(items, dry_run=args.dry_run)

    # Post to YouTube Shorts as well
    print(f"\n🎥 {label}Posting to YouTube Shorts...\n")
    yt_results = post_all_shorts(items, dry_run=args.dry_run)

    ok  = [r for r in results if r.get("success")]
    bad = [r for r in results if not r.get("success")]
    yt_ok = [r for r in yt_results if r.get("success")]
    yt_bad = [r for r in yt_results if not r.get("success")]

    print(f"\n── Social Summary ──────────────────────────")
    print(f"  TikTok/Instagram Posted:  {len(ok)}")
    print(f"  TikTok/Instagram Failed:  {len(bad)}")
    print(f"  YouTube Shorts Posted:    {len(yt_ok)}")
    print(f"  YouTube Shorts Failed:    {len(yt_bad)}")

    if not args.dry_run:
        pick_map = {v["pick"].match: v["pick"] for v in video_results if v.get("video_path")}
        for r in ok:
            pick = pick_map.get(r.get("match"))
            if pick:
                for platform in ["tiktok", "instagram"]:
                    if platform in r.get("platforms", []):
                        log_post(pick, platform, r.get("request_id"))
        
        for r in yt_ok:
            pick = pick_map.get(r.get("match"))
            if pick:
                log_post(pick, "youtube", r.get("video_id"))



def _cmd_stats():
    totals = total_stats()
    print("\n── All-Time Stats ──────────────────────────")
    print(f"  Total posted:    {totals['total_posted']}")
    print(f"  Days active:     {totals['days_active']}")
    print(f"  Wins:            {totals['total_wins']}")
    print(f"  Losses:          {totals['total_losses']}")
    print(f"  Avg confidence:  {totals['avg_confidence']}%")
    print(f"  Avg edge:        {totals['avg_edge']}%")

    print("\n── Last 7 Days (by date + platform) ────────")
    rows = weekly_summary()
    if not rows:
        print("  No data yet.")
    else:
        for r in rows:
            wl = f"  W{r['wins']} L{r['losses']}" if (r['wins'] or r['losses']) else "  (no results logged)"
            print(f"  {r['date']}  {r['platform']:<12}  {r['posted']} picks{wl}")

    print("\n── Today ───────────────────────────────────")
    today = get_today()
    if not today:
        print("  Nothing posted today yet.")
    else:
        for r in today:
            result = f"  [{r['result']}]" if r['result'] else ""
            print(f"  {r['platform']:<12}  {r['match']}  {r['label']} @ {r['odds']}{result}")
    print()


def _cmd_log_result(args):
    from datetime import date as _date
    target_date = args.date or _date.today().isoformat()
    match_query = args.match.lower()

    recent = get_recent(30)
    candidates = [
        r for r in recent
        if match_query in r["match"].lower() and r["date"] == target_date
    ]

    if not candidates:
        # Relax date filter if no match found on that date
        candidates = [r for r in recent if match_query in r["match"].lower()]

    if not candidates:
        print(f"No posts found matching '{args.match}'. Run --stats to see recent posts.")
        return

    # Deduplicate by match+date (update all platforms at once)
    updated_matches = set()
    for r in candidates:
        key = (r["match"], r["date"])
        if key not in updated_matches:
            set_result(r["match"], r["date"], args.result)
            updated_matches.add(key)
            print(f"  ✓ {r['date']}  {r['match']}  → {args.result.upper()}")

    if not updated_matches:
        print("No records updated.")


def main():
    parser = argparse.ArgumentParser(description="Epifani Growth Engine")

    parser.add_argument("--list-picks",     action="store_true", help="Show today's picks")
    parser.add_argument("--journey-script",  action="store_true", help="Generate a Founder's Journey voiceover script (needs --milestone)")
    parser.add_argument("--journey-video",   action="store_true", help="Generate the journey script AND build the branded video (needs --milestone)")
    parser.add_argument("--milestone",       type=str, metavar="TEXT", help="Today's building update for the journey script")
    parser.add_argument("--cta",             type=str, choices=["site", "comment"], default=None,
                        help="Script ending: 'site' (epifanii.com link, default) or 'comment' (comment-gate → DM)")
    parser.add_argument("--generate-cards", action="store_true", help="Build prediction card images")
    parser.add_argument("--build-videos",   action="store_true", help="Build branded videos via MPT")
    parser.add_argument("--post-twitter",   action="store_true", help="Post tweet threads to Twitter/X")
    parser.add_argument("--post-social",    action="store_true", help="Post videos to TikTok + Instagram")
    parser.add_argument("--run-all",        action="store_true", help="Full pipeline: cards + videos + all platforms")
    parser.add_argument("--dry-run",        action="store_true", help="Preview without posting")
    parser.add_argument("--no-corners",     action="store_true", help="Exclude corners market predictions")
    parser.add_argument("--top",            type=int, default=None, metavar="N", help="Only use top N picks (default: all)")
    parser.add_argument("--stats",          action="store_true", help="Show posting analytics summary")
    parser.add_argument("--log-result",     action="store_true", help="Record win/loss for a posted pick")
    parser.add_argument("--match",          type=str,            metavar="NAME", help="Match name (partial match OK) for --log-result")
    parser.add_argument("--result",         type=str,            choices=["win", "loss", "void"], help="Outcome for --log-result")
    parser.add_argument("--date",           type=str,            metavar="YYYY-MM-DD", help="Post date for --log-result (default: today)")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return

    try:
        if args.stats:
            _cmd_stats()
            return

        if args.log_result:
            if not args.match or not args.result:
                print("Usage: --log-result --match 'Arsenal vs Chelsea' --result win")
                return
            _cmd_log_result(args)
            return

        if args.list_picks:
            cmd_list_picks(args)

        if args.journey_script:
            cmd_journey_script(args)
            return

        if args.journey_video:
            cmd_journey_video(args)
            return

        picks = None

        if args.generate_cards or args.run_all:
            cards = cmd_generate_cards(args)
            picks = _picks(args) if cards else None
        else:
            cards = None

        if args.build_videos or args.run_all:
            video_results = cmd_build_videos(args)
        else:
            video_results = None

        if args.post_twitter or args.run_all:
            if picks is None:
                picks = _picks(args)
            cmd_post_twitter(args, cards=cards, picks=picks)

        if args.post_social or args.run_all:
            cmd_post_social(args, video_results=video_results)

    finally:
        stop_mpt()


if __name__ == "__main__":
    main()
