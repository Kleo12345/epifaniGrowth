#!/usr/bin/env python3
"""
Push Epifani's social stats to the Bot Dashboard's "Social" tab.

Every connected channel's whole account, not just the journey videos: all-time
views / likes / comments / shares summed over every post, follower count, and a
per-post list (journey posts tagged with their calendar day). The journey
daemon runs push() every 30 minutes; the dashboard keeps the history for charts.

Config: ~/.bot_dashboard.env (DASH_URL, PUSH_SECRET) — the same file the trading
bots' push_snapshot.py uses. Without it, push() does nothing.

Run by hand (from engine/):
  python -m tools.push_social --print     # show the snapshot, send nothing
  python -m tools.push_social             # collect and send
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ENG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENG))

from core import analytics
from core.social_publish import configured_platforms
from publishers import youtube_publisher
from publishers import upload_post_publisher as ig_tiktok

DASH_ENV = Path.home() / ".bot_dashboard.env"
STATS = ("views", "likes", "comments", "shares")


def _post(platform, pid, title, url, date, views=None, likes=None, comments=None, shares=None):
    return {"platform": platform, "id": str(pid), "title": (title or "").strip().split("\n")[0][:90],
            "url": url, "date": date, "views": views, "likes": likes, "comments": comments, "shares": shares}


def _instagram() -> tuple[list, int | None]:
    # ponytail: one insights call per post every 30 min; Instagram allows ~200 calls/hour,
    # so past ~90 posts limit this to recent posts and keep older totals from the last run.
    tok = os.environ["INSTAGRAM_ACCESS_TOKEN"]
    media, url = [], f"{ig_tiktok.IG_GRAPH}/me/media"
    params = {"fields": "id,caption,permalink,timestamp", "limit": 50, "access_token": tok}
    while url:
        d = requests.get(url, params=params, timeout=20).json()
        if "error" in d:
            raise RuntimeError(d["error"].get("message", d["error"]))
        media += d.get("data", [])
        url, params = d.get("paging", {}).get("next"), None  # `next` already carries the params
    posts = []
    for m in media:
        ins = {}
        for metrics in ("views,likes,comments,shares", "likes,comments"):  # older/image posts lack views
            r = requests.get(f"{ig_tiktok.IG_GRAPH}/{m['id']}/insights",
                             params={"metric": metrics, "access_token": tok}, timeout=20)
            if r.ok:
                ins = {x["name"]: x["values"][0]["value"] for x in r.json().get("data", [])}
                break
        posts.append(_post("instagram", m["id"], m.get("caption"), m.get("permalink"), m.get("timestamp"),
                           ins.get("views"), ins.get("likes"), ins.get("comments"), ins.get("shares")))
    me = requests.get(f"{ig_tiktok.IG_GRAPH}/me", params={"fields": "followers_count", "access_token": tok},
                      timeout=20).json()
    return posts, me.get("followers_count")


def _youtube() -> tuple[list, int | None]:
    h = {"Authorization": f"Bearer {youtube_publisher._get_access_token()}"}
    api = "https://www.googleapis.com/youtube/v3"
    ch = requests.get(f"{api}/channels", headers=h, params={"part": "statistics,contentDetails", "mine": "true"},
                      timeout=20).json()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        d = requests.get(f"{api}/playlistItems", headers=h, timeout=20,
                         params={"part": "contentDetails", "playlistId": uploads, "maxResults": 50,
                                 **({"pageToken": token} if token else {})}).json()
        ids += [i["contentDetails"]["videoId"] for i in d.get("items", [])]
        token = d.get("nextPageToken")
        if not token:
            break
    posts = []
    for i in range(0, len(ids), 50):
        d = requests.get(f"{api}/videos", headers=h, timeout=20,
                         params={"part": "statistics,snippet", "id": ",".join(ids[i:i + 50])}).json()
        for v in d.get("items", []):
            s = v["statistics"]
            posts.append(_post("youtube", v["id"], v["snippet"]["title"], f"https://youtube.com/shorts/{v['id']}",
                               v["snippet"]["publishedAt"], int(s.get("viewCount", 0)),
                               int(s.get("likeCount", 0)), int(s.get("commentCount", 0))))
    subs = ch["statistics"].get("subscriberCount")
    return posts, int(subs) if subs is not None else None


def _tiktok() -> tuple[list, int | None]:
    h = {"Authorization": f"Bearer {ig_tiktok.tiktok_access_token()}", "Content-Type": "application/json"}
    fields = "id,create_time,title,share_url,view_count,like_count,comment_count,share_count"
    posts, cursor = [], None
    while True:
        d = requests.post("https://open.tiktokapis.com/v2/video/list/", params={"fields": fields}, headers=h,
                          json={"max_count": 20, **({"cursor": cursor} if cursor else {})}, timeout=20).json()
        if d.get("error", {}).get("code") not in (None, "ok"):
            raise RuntimeError(d["error"].get("message") or d["error"]["code"])
        data = d.get("data", {})
        for v in data.get("videos", []):
            posts.append(_post("tiktok", v["id"], v.get("title"), v.get("share_url"),
                               datetime.fromtimestamp(v["create_time"], timezone.utc).isoformat(),
                               v.get("view_count"), v.get("like_count"), v.get("comment_count"), v.get("share_count")))
        if not data.get("has_more"):
            break
        cursor = data.get("cursor")
    u = requests.get("https://open.tiktokapis.com/v2/user/info/", headers=h,
                     params={"fields": "follower_count"}, timeout=20).json()
    return posts, u.get("data", {}).get("user", {}).get("follower_count")


_COLLECTORS = {"instagram": _instagram, "youtube": _youtube, "tiktok": _tiktok}


def snapshot() -> dict:
    """{platforms: {p: {followers, views, likes, comments, shares, posts}}, posts: [...], errors: {p: msg}}"""
    day_of = {(r["platform"], r["post_id"]): r["day"] for r in analytics.social_posts_since(100000) if r["post_id"]}
    platforms, posts, errors = {}, [], {}
    for p in configured_platforms():
        if p not in _COLLECTORS:
            continue
        try:
            items, followers = _COLLECTORS[p]()
        except Exception as e:
            errors[p] = str(e)[:200]
            continue
        for it in items:
            it["day"] = day_of.get((p, it["id"]))
        platforms[p] = {"followers": followers, "posts": len(items),
                        **{k: sum(it[k] or 0 for it in items) for k in STATS}}
        posts += items
    posts.sort(key=lambda x: x["date"] or "", reverse=True)
    return {"platforms": platforms, "posts": posts[:200], "errors": errors}


def _dash_config() -> dict:
    if not DASH_ENV.exists():
        return {}
    pairs = (line.split("=", 1) for line in DASH_ENV.read_text().splitlines() if "=" in line)
    return {k.strip(): v.strip() for k, v in pairs}


def push() -> bool:
    """Collect and send to the dashboard. Quietly skips when ~/.bot_dashboard.env is missing."""
    cfg = _dash_config()
    if not cfg.get("DASH_URL") or not cfg.get("PUSH_SECRET"):
        return False
    r = requests.post(f"{cfg['DASH_URL'].rstrip('/')}/api/social", json=snapshot(),
                      headers={"x-push-secret": cfg["PUSH_SECRET"]}, timeout=30)
    r.raise_for_status()
    return True


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ENG / ".env")
    if "--print" in sys.argv:
        print(json.dumps(snapshot(), indent=1, default=str))
    else:
        print("pushed" if push() else "no ~/.bot_dashboard.env — nothing sent")
