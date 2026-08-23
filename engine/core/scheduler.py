"""
Daily automation scheduler.
Runs the full pipeline automatically every day at 09:00 Europe/Athens (GMT+2).

Schedule:
  08:50 — Fetch top 3 picks + build cards
  09:00 — Post Twitter threads
  09:10 — Build videos (MPT)
  09:30 — Post to TikTok + Instagram via Upload-Post

Start with:
  conda activate epifani-growth
  python scheduler.py
"""
import sys
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.prediction_fetcher       import fetch_picks
from core.image_builder            import build_all_cards
from core.script_generator         import generate_all_threads
from core.video_builder            import build_all_videos, stop_mpt
from core.analytics                import log_post
from publishers.twitter_publisher  import post_all_threads
from publishers.upload_post_publisher import post_all_videos
from publishers.youtube_publisher import post_all_shorts

TIMEZONE       = "Europe/Athens"
TOP_N          = 3
EXCLUDE_CORNERS = True

scheduler = BlockingScheduler(timezone=TIMEZONE)


def _caption(pick) -> str:
    return (
        f"{pick.match} — {pick.label} @ {pick.odds} | "
        f"{pick.confidence_pct}% AI Confidence\n\n"
        f"Get all picks free → epifanii.com/?ref=tiktok #football #betting #AI"
    )


def job_fetch_and_cards():
    """08:50 — Fetch top picks and generate image cards."""
    print("\n[08:50] Fetching today's top picks and building cards...")
    try:
        picks = fetch_picks(exclude_corners=EXCLUDE_CORNERS, top=TOP_N)
        if not picks:
            print("  No qualifying picks today.")
            return
        build_all_cards(picks)
        print(f"  ✓ Cards ready for {len(picks)} picks")
    except Exception as e:
        print(f"  ✗ Failed: {e}")


def job_post_twitter():
    """09:00 — Post Twitter threads for top picks."""
    print("\n[09:00] Posting to Twitter/X...")
    try:
        picks   = fetch_picks(exclude_corners=EXCLUDE_CORNERS, top=TOP_N)
        if not picks:
            return
        cards   = build_all_cards(picks)
        threads = generate_all_threads(picks)
        pairs   = [
            {"thread": t, "square": c["square"], "story": c["story"]}
            for t, c in zip(threads, cards)
        ]
        results = post_all_threads(pairs)
        pick_map = {p.match: p for p in picks}
        for r in results:
            if r["success"]:
                pick = pick_map.get(r["match"])
                if pick:
                    post_id = r["urls"][0].split("/")[-1] if r.get("urls") else None
                    log_post(pick, "twitter", post_id)
    except Exception as e:
        print(f"  ✗ Twitter posting failed: {e}")


def job_post_video():
    """09:10 — Build videos and post to TikTok + Instagram + YouTube Shorts."""
    print("\n[09:10] Building and posting videos...")
    try:
        picks   = fetch_picks(exclude_corners=EXCLUDE_CORNERS, top=TOP_N)
        if not picks:
            return
        videos  = build_all_videos(picks)

        items = [
            {
                "video_path": v["video_path"],
                "caption":    _caption(v["pick"]),
                "match":      v["pick"].match,
            }
            for v in videos if v.get("video_path")
        ]
        results = post_all_videos(items)
        yt_results = post_all_shorts(items)
        
        pick_map = {v["pick"].match: v["pick"] for v in videos if v.get("video_path")}
        for r in results:
            if r.get("success"):
                pick = pick_map.get(r.get("match"))
                if pick:
                    for platform in ["tiktok", "instagram"]:
                        if platform in r.get("platforms", []):
                            log_post(pick, platform, r.get("request_id"))
                            
        for r in yt_results:
            if r.get("success"):
                pick = pick_map.get(r.get("match"))
                if pick:
                    log_post(pick, "youtube", r.get("video_id"))
    except Exception as e:
        print(f"  ✗ Video posting failed: {e}")

    finally:
        stop_mpt()


def register_jobs():
    scheduler.add_job(job_fetch_and_cards, CronTrigger(hour=8,  minute=50, timezone=TIMEZONE), id="fetch_cards")
    scheduler.add_job(job_post_twitter,    CronTrigger(hour=9,  minute=0,  timezone=TIMEZONE), id="post_twitter")
    scheduler.add_job(job_post_video,      CronTrigger(hour=9,  minute=10, timezone=TIMEZONE), id="post_video")


def run():
    register_jobs()
    print(f"Epifani scheduler started — timezone: {TIMEZONE}")
    print("  08:50 → fetch + cards")
    print("  09:00 → Twitter threads")
    print("  09:10 → videos → TikTok + Instagram")
    print("\nPress Ctrl+C to stop.\n")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")
        stop_mpt()


if __name__ == "__main__":
    run()
