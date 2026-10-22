"""
Nightly growth report — run by journey_daemon.py at 22:30 Europe/Athens.

  1. collect()  pulls per-post numbers (views/likes/comments/shares/saves) and
                follower counts from every connected platform into analytics.db.
  2. digest()   turns the latest snapshot + change since yesterday into plain text,
                with each post's format (kind/fam/hook) and its spoken opening line.
  3. analyze()  hands the digest to Claude Code headless (`claude -p`, no tools) for a
                verdict + what to change tomorrow. If Claude isn't reachable the report
                still goes out with the raw numbers.

Reports are saved to assets/output/reports/YYYY-MM-DD.md; the previous one is fed
back in so the analysis can check whether yesterday's advice moved anything.

Run by hand:  python -m core.daily_report     (from engine/)
"""
import json
import os
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from core import analytics
from core.content_calendar import calendar_entry
from core.script_generator import project_day
from publishers import twitter_publisher, youtube_publisher
from publishers import upload_post_publisher as ig_tiktok

ENG = Path(__file__).resolve().parents[1]
REPORTS_DIR = ENG / "assets" / "output" / "reports"
LOOKBACK_DAYS = 14   # keep tracking a post this long after it goes up
X_LOOKBACK_DAYS = 3  # X's free API tier allows ~100 post reads/month — only track fresh tweets
TZ = ZoneInfo("Europe/Athens")


# ── Per-platform collectors: each returns ({post_id: metrics}, followers) ──

def _instagram(post_ids: list[str]) -> tuple[dict, int | None]:
    token = os.environ["INSTAGRAM_ACCESS_TOKEN"]
    out = {}
    for pid in post_ids:
        data = None
        for metrics in ("views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time",
                        "reach,likes,comments,shares,saved"):  # fallback if a metric is unavailable
            r = requests.get(f"{ig_tiktok.IG_GRAPH}/{pid}/insights",
                             params={"metric": metrics, "access_token": token}, timeout=20)
            if r.ok:
                data = {d["name"]: d["values"][0]["value"] for d in r.json().get("data", [])}
                break
        if data is None:
            r.raise_for_status()
        out[pid] = {"views": data.get("views", data.get("reach")), "likes": data.get("likes"),
                    "comments": data.get("comments"), "shares": data.get("shares"),
                    "saves": data.get("saved"),
                    "extra": json.dumps({k: data[k] for k in ("reach", "ig_reels_avg_watch_time") if k in data})}
    me = requests.get(f"{ig_tiktok.IG_GRAPH}/me",
                      params={"fields": "followers_count", "access_token": token}, timeout=20)
    me.raise_for_status()
    return out, me.json().get("followers_count")


def _youtube(post_ids: list[str]) -> tuple[dict, int | None]:
    headers = {"Authorization": f"Bearer {youtube_publisher._get_access_token()}"}
    out = {}
    if post_ids:
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers=headers,
                         params={"part": "statistics", "id": ",".join(post_ids[:50])}, timeout=20)
        r.raise_for_status()
        for v in r.json().get("items", []):
            s = v["statistics"]
            out[v["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                            "comments": int(s.get("commentCount", 0))}
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels", headers=headers,
                      params={"part": "statistics", "mine": "true"}, timeout=20)
    ch.raise_for_status()
    items = ch.json().get("items") or [{}]
    subs = items[0].get("statistics", {}).get("subscriberCount")
    return out, int(subs) if subs is not None else None


def _x(post_ids: list[str]) -> tuple[dict, int | None]:
    client, _ = twitter_publisher._client()
    out = {}
    if post_ids:
        resp = client.get_tweets(post_ids[:100], tweet_fields=["public_metrics"])
        for t in resp.data or []:
            m = t.public_metrics
            out[str(t.id)] = {"views": m.get("impression_count"), "likes": m.get("like_count"),
                              "comments": m.get("reply_count"),
                              "shares": m.get("retweet_count", 0) + m.get("quote_count", 0),
                              "saves": m.get("bookmark_count")}
    me = client.get_me(user_fields=["public_metrics"])
    return out, me.data.public_metrics.get("followers_count")


def _tiktok(rows: list[dict]) -> tuple[dict, int | None]:
    """Inbox drafts have no id until you post them in the app, so first link each
    un-linked tiktok row to the earliest unclaimed video created on/after its date."""
    headers = {"Authorization": f"Bearer {ig_tiktok.tiktok_access_token()}",
               "Content-Type": "application/json"}
    r = requests.post("https://open.tiktokapis.com/v2/video/list/",
                      params={"fields": "id,create_time,share_url,view_count,like_count,comment_count,share_count"},
                      json={"max_count": 20}, headers=headers, timeout=20)
    r.raise_for_status()
    videos = sorted(r.json().get("data", {}).get("videos", []), key=lambda v: v["create_time"])
    claimed = {row["post_id"] for row in rows if row["post_id"]}
    for row in rows:
        if row["post_id"]:
            continue
        for v in videos:
            made = datetime.fromtimestamp(v["create_time"], TZ).date().isoformat()
            if v["id"] not in claimed and made >= row["date"]:
                analytics.update_social_post(row["id"], v["id"], v.get("share_url"))
                row["post_id"] = v["id"]
                claimed.add(v["id"])
                break
    out = {v["id"]: {"views": v.get("view_count"), "likes": v.get("like_count"),
                     "comments": v.get("comment_count"), "shares": v.get("share_count")}
           for v in videos if v["id"] in claimed}
    u = requests.get("https://open.tiktokapis.com/v2/user/info/", headers=headers,
                     params={"fields": "follower_count"}, timeout=20)
    u.raise_for_status()
    return out, u.json().get("data", {}).get("user", {}).get("follower_count")


_COLLECTORS = {"instagram": _instagram, "youtube": _youtube, "x": _x}


def collect(today: str | None = None) -> dict:
    """Snapshot every connected platform. Returns {platform: error message} for failures."""
    from core.social_publish import configured_platforms
    today = today or date.today().isoformat()
    rows = analytics.social_posts_since(LOOKBACK_DAYS)
    x_cutoff = (date.fromisoformat(today) - timedelta(days=X_LOOKBACK_DAYS)).isoformat()
    errors = {}
    for p in configured_platforms():
        mine = [r for r in rows if r["platform"] == p]
        try:
            if p == "tiktok":
                metrics, followers = _tiktok(mine)
            else:
                ids = [r["post_id"] for r in mine if r["post_id"] and (p != "x" or r["date"] >= x_cutoff)]
                metrics, followers = _COLLECTORS[p](ids)
        except Exception as e:
            # Instagram puts the token in the URL, and the URL lands in the error text.
            errors[p] = re.sub(r"(access_token=)[^&\s;]+", r"\1***", str(e))[:200]
            continue
        for pid, m in metrics.items():
            analytics.save_post_metrics(today, p, pid, m)
        analytics.save_account_metrics(today, p, followers)
    return errors


# ── Digest + analysis ────────────────────────────────────────────────

def _fmt_metrics(now: dict, before: dict | None) -> str:
    parts = []
    for k in ("views", "likes", "comments", "shares", "saves"):
        v = now.get(k)
        if v is None:
            continue
        prev = (before or {}).get(k)
        parts.append(f"{k} {v}" + (f" ({v - prev:+d})" if prev is not None and v != prev else ""))
    extra = json.loads(now.get("extra") or "{}")
    if "ig_reels_avg_watch_time" in extra:  # milliseconds
        parts.append(f"avg_watch {extra['ig_reels_avg_watch_time'] / 1000:.1f}s")
    return ", ".join(parts) or "no numbers yet"


def digest(today: str | None = None, errors: dict | None = None) -> str:
    today = today or date.today().isoformat()
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    week_ago = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
    day = project_day()
    lines = [f"Date: {today} — project day {day}."]
    nxt = calendar_entry(day + 1)
    if nxt:
        lines.append(f"Tomorrow's calendar: Day {day + 1} [{nxt['kind']}/{nxt['fam']}/{nxt['hook']}] — {nxt['topic']}")

    f_now, f_y, f_w = analytics.followers_on(today), analytics.followers_on(yesterday), analytics.followers_on(week_ago)
    lines.append("\nFOLLOWERS:")
    for p, n in sorted(f_now.items()):
        d1 = f" ({n - f_y[p]:+d} today)" if f_y.get(p) is not None and n is not None else ""
        d7 = f" ({n - f_w[p]:+d} in 7d)" if f_w.get(p) is not None and n is not None else ""
        lines.append(f"- {p}: {n}{d1}{d7}")

    m_now, m_y = analytics.post_metrics_on(today), analytics.post_metrics_on(yesterday)
    rows = analytics.social_posts_since(LOOKBACK_DAYS)
    lines.append("\nPOSTS (latest numbers; + = growth since yesterday):")
    by_day: dict = {}
    for r in rows:
        by_day.setdefault((r["day"], r["date"]), []).append(r)
    for (d, posted), group in sorted(by_day.items(), key=lambda kv: kv[0][1], reverse=True):
        g = group[0]
        age = (date.fromisoformat(today) - date.fromisoformat(posted)).days
        opener = (g["voiceover"] or "").split(".")[0][:140]
        lines.append(f"- Day {d} [{g['kind']}/{g['fam']}/{g['hook']}] posted {posted} ({age}d old)")
        lines.append(f'  opening line: "{opener}"')
        for r in group:
            key = (r["platform"], r["post_id"])
            stats = _fmt_metrics(m_now[key], m_y.get(key)) if key in m_now else (
                "draft not posted in the app yet" if r["platform"] == "tiktok" and not r["post_id"]
                else "no numbers yet")
            lines.append(f"  {r['platform']}: {stats}")
    if not rows:
        lines.append("- nothing posted yet")
    if errors:
        lines.append("\nCOULD NOT COLLECT: " + "; ".join(f"{p}: {e}" for p, e in errors.items()))
    return "\n".join(lines)


_ANALYST = """You are the growth analyst for Epifani, a solo founder's AI football-prediction
platform (epifanii.com, $30/mo subscription). Socials are top-of-funnel only: short daily
"Founder's Journey" build-in-public videos (TikTok, Instagram Reels, YouTube Shorts, X),
following a 44-day content calendar. Each post is tagged [kind/fam/hook]: kind = journey
(daily topic) or record (weekly model track-record); fam = content family; hook = opening style.

Hard constraint: the account must read as a developer building an AI in public, never a
tipster/betting account (platforms remove betting-advice content). Never suggest betting
language, urgency, or win-rate flexing without sample sizes.

Below is today's data. Write tonight's report for the founder's phone (Telegram, plain
text, no markdown tables, under 1500 characters):

VERDICT: one line — on track / too early to tell / off track, and why.
WHAT WORKED: 1-3 bullets, tied to specific posts/hooks/platforms and numbers.
WHAT DIDN'T: 1-3 bullets.
DO TOMORROW: max 3 concrete changes (hook, length, platform, posting time, caption, CTA),
  considering tomorrow's calendar topic.

Be honest about small samples: posts under 48h old and accounts under ~1k followers are
noisy — say "too early" rather than invent a trend. Compare against the previous report's
advice when there is one.

{previous}

DATA:
{digest}"""


def _claude_bin() -> str | None:
    # systemd --user units often lack ~/.local/bin on PATH, so check there too.
    local = Path.home() / ".local" / "bin" / "claude"
    return os.getenv("CLAUDE_BIN") or shutil.which("claude") or (str(local) if local.exists() else None)


def analyze(digest_text: str, previous: str = "") -> str | None:
    """Claude Code headless, tools disabled — pure analysis of the text it's given."""
    exe = _claude_bin()
    if not exe:
        return None
    prompt = _ANALYST.format(
        previous=f"PREVIOUS REPORT:\n{previous[-1500:]}" if previous else "(No previous report.)",
        digest=digest_text,
    )
    try:
        out = subprocess.run([exe, "-p", "--tools", "", "--no-session-persistence"],
                             input=prompt, capture_output=True, text=True, timeout=600,
                             cwd=ENG.parent)
    except Exception as e:
        print(f"  ⚠ claude analysis failed: {e}")
        return None
    if out.returncode != 0 or not out.stdout.strip():
        print(f"  ⚠ claude exited {out.returncode}: {out.stderr[-300:]}")
        return None
    return out.stdout.strip()


def daily_report(today: str | None = None) -> str:
    """collect → digest → analyze → save. Returns the text to send to Telegram."""
    today = today or date.today().isoformat()
    errors = collect(today)
    text = digest(today, errors)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    prev_files = sorted(p for p in REPORTS_DIR.glob("*.md") if p.stem < today)
    previous = prev_files[-1].read_text(encoding="utf-8").split("## Numbers")[0] if prev_files else ""
    analysis = analyze(text, previous) or "(Claude analysis unavailable tonight — raw numbers below.)"
    (REPORTS_DIR / f"{today}.md").write_text(
        f"# Growth report {today}\n\n{analysis}\n\n## Numbers\n\n{text}\n", encoding="utf-8")
    return f"📊 Growth report — {today}\n\n{analysis}\n\n— numbers —\n{text}"


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ENG / ".env")
    print(daily_report())
