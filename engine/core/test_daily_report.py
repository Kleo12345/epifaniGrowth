"""
Assert-based self-check for core/daily_report.py — temp DB, no network. Run with:
  python core/test_daily_report.py
"""
import sys
import types
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import analytics
from core import daily_report as dr


def demo():
    analytics.DB_PATH = Path("/tmp/_daily_report_test.db")
    analytics.DB_PATH.unlink(missing_ok=True)
    dr.project_day = lambda: 1
    dr.calendar_entry = lambda d: {"kind": "journey", "fam": "build", "hook": "STRUGGLE", "topic": "next"}
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    meta = {"day": 1, "kind": "journey", "fam": "build", "hook": "CONFESSION",
            "caption": "c", "voiceover": "I almost quit. Then the model hit."}
    analytics.log_social_post("instagram", "ig1", "https://ig/1", meta)
    analytics.log_social_post("tiktok", None, None, meta)  # inbox draft, no id yet

    # TikTok: the draft row gets linked to the first video created on/after its date,
    # skipping one made before it.
    ts = lambda d: int(datetime.fromisoformat(d).replace(hour=12, tzinfo=ZoneInfo("Europe/Athens")).timestamp())
    videos = [{"id": "old", "create_time": ts("2020-01-01")},
              {"id": "tt1", "create_time": ts(today), "share_url": "https://tt/1", "view_count": 50}]
    ok = lambda payload: types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
    dr.requests = types.SimpleNamespace(
        post=lambda *a, **k: ok({"data": {"videos": videos}}),
        get=lambda *a, **k: ok({"data": {"user": {"follower_count": 7}}}),
    )
    dr.ig_tiktok = types.SimpleNamespace(tiktok_access_token=lambda: "t")
    rows = [r for r in analytics.social_posts_since(1) if r["platform"] == "tiktok"]
    metrics, followers = dr._tiktok(rows)
    assert metrics == {"tt1": {"views": 50, "likes": None, "comments": None, "shares": None}}, metrics
    assert followers == 7
    linked = [r for r in analytics.social_posts_since(1) if r["platform"] == "tiktok"][0]
    assert linked["post_id"] == "tt1" and linked["url"] == "https://tt/1", linked

    # Digest shows per-post growth since yesterday (both directions) and follower deltas.
    analytics.save_post_metrics(yesterday, "instagram", "ig1", {"views": 100, "likes": 5})
    analytics.save_account_metrics(yesterday, "instagram", 40)
    analytics.save_post_metrics(today, "instagram", "ig1", {"views": 340, "likes": 4})
    analytics.save_account_metrics(today, "instagram", 45)
    text = dr.digest(today, errors={"youtube": "401"})
    assert "instagram: 45 (+5 today)" in text, text
    assert "views 340 (+240)" in text and "likes 4 (-1)" in text, text
    assert 'opening line: "I almost quit"' in text, text
    assert "COULD NOT COLLECT: youtube: 401" in text, text

    analytics.DB_PATH.unlink(missing_ok=True)
    print("OK — daily_report links TikTok drafts and computes deltas")


if __name__ == "__main__":
    demo()
