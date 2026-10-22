"""
Post an approved Founder's Journey video to every connected platform.

Called by journey_daemon.py when you tap Approve in Telegram. Each platform is
independent: one failing (expired token, API hiccup) never blocks the others,
and the daemon offers a "Retry failed" button for just the ones that failed.
Every successful post is logged to analytics.db (social_posts) so the nightly
report (core/daily_report.py) can pull its numbers.

Platforms count as connected when their credentials are in engine/.env; list any
you want to pause in SOCIAL_SKIP (e.g. SOCIAL_SKIP=youtube,x).
"""
import os

import requests

from core import analytics
from core.script_generator import JourneyScript, platform_captions
from publishers import twitter_publisher, youtube_publisher
from publishers import upload_post_publisher as ig_tiktok

PLATFORMS = ("instagram", "tiktok", "youtube", "x")


def configured_platforms() -> list[str]:
    connected = {
        "instagram": bool(os.getenv("INSTAGRAM_ACCESS_TOKEN")),
        "tiktok": ig_tiktok.tiktok_configured(),
        "youtube": youtube_publisher.is_configured(),
        "x": twitter_publisher.is_configured(),
    }
    skip = {p.strip().lower() for p in os.getenv("SOCIAL_SKIP", "").split(",")}
    return [p for p in PLATFORMS if connected[p] and p not in skip]


def _instagram_permalink(media_id: str) -> str | None:
    try:
        r = requests.get(f"{ig_tiktok.IG_GRAPH}/{media_id}",
                         params={"fields": "permalink",
                                 "access_token": os.environ["INSTAGRAM_ACCESS_TOKEN"]},
                         timeout=20)
        return r.json().get("permalink")
    except Exception:
        return None


def _post_one(platform: str, video_path: str, caption: str, hashtags: str) -> tuple[str | None, str | None]:
    """Returns (post_id, url). TikTok returns (None, None): an inbox draft has no public
    id until you tap Post in the app — daily_report links it up afterwards."""
    full = f"{caption}\n\n{hashtags}".strip()
    if platform == "instagram":
        media_id = ig_tiktok._post_instagram(video_path, full)
        return media_id, _instagram_permalink(media_id)
    if platform == "tiktok":
        ig_tiktok._post_tiktok(video_path, full)
        return None, None
    if platform == "youtube":
        title = caption.splitlines()[0] if caption else "Building an AI that predicts football"
        video_id = youtube_publisher.post_short(video_path, title=title, description=full)
        return video_id, f"https://youtube.com/shorts/{video_id}"
    if platform == "x":
        tweet_id = twitter_publisher.post_video(video_path, caption, hashtags)
        return tweet_id, f"https://x.com/i/web/status/{tweet_id}"
    raise ValueError(f"Unknown platform: {platform}")


def publish(video_path: str, script: dict, meta: dict, platforms: list[str],
            captions: dict | None = None) -> dict:
    """Post to each platform in `platforms`.

    script   : {day, milestone, voiceover, caption, hashtags} as saved in the daemon state.
    meta     : {kind, fam, hook} — logged with each post so the report can compare formats.
    captions : the per-platform captions previewed in Telegram, so what you approved is
               exactly what's posted; written fresh only if missing.
    Returns {platform: {"ok": bool, "url": str|None, "caption": str, "error": str|None}}.
    """
    js = JourneyScript(day=script.get("day", 0), milestone=script.get("milestone", ""),
                       voiceover=script.get("voiceover", ""), caption=script.get("caption", ""),
                       hashtags=script.get("hashtags", ""), picks=[])
    captions = captions or platform_captions(js)
    results = {}
    for p in platforms:
        cap = captions.get(p, {"caption": js.caption, "hashtags": js.hashtags})
        try:
            post_id, url = _post_one(p, video_path, cap["caption"], cap["hashtags"])
        except Exception as e:
            print(f"  ✗ {p} post failed: {e}")
            results[p] = {"ok": False, "url": None, "caption": cap["caption"], "error": str(e)[:300]}
            continue
        analytics.log_social_post(p, post_id, url, {
            **meta, "day": js.day, "caption": cap["caption"], "voiceover": js.voiceover,
        })
        results[p] = {"ok": True, "url": url, "caption": f"{cap['caption']}\n\n{cap['hashtags']}",
                      "error": None}
    return results
