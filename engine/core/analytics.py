"""
Epifani Analytics Tracker — logs every posted pick to a local SQLite database.

Usage:
  from core.analytics import log_post, get_today, weekly_summary
  log_post(pick, platform="twitter", post_id="1234567890")
"""
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "analytics.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at     TEXT    DEFAULT (datetime('now')),
                date           TEXT    NOT NULL,
                match          TEXT    NOT NULL,
                league         TEXT,
                label          TEXT,
                odds           REAL,
                confidence_pct INTEGER,
                edge_pct       REAL,
                tier           TEXT,
                platform       TEXT    NOT NULL,
                post_id        TEXT,
                result         TEXT
            )
        """)
        # Founder's Journey videos posted to socials — one row per platform per video.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS social_posts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                posted_at   TEXT    DEFAULT (datetime('now')),
                date        TEXT    NOT NULL,
                day         INTEGER,
                kind        TEXT,
                fam         TEXT,
                hook        TEXT,
                platform    TEXT    NOT NULL,
                post_id     TEXT,
                url         TEXT,
                caption     TEXT,
                voiceover   TEXT
            )
        """)
        # Daily snapshots, so the nightly report can show growth since yesterday.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS post_metrics (
                snapshot_date TEXT NOT NULL,
                platform      TEXT NOT NULL,
                post_id       TEXT NOT NULL,
                views         INTEGER,
                likes         INTEGER,
                comments      INTEGER,
                shares        INTEGER,
                saves         INTEGER,
                extra         TEXT,
                PRIMARY KEY (snapshot_date, platform, post_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS account_metrics (
                snapshot_date TEXT NOT NULL,
                platform      TEXT NOT NULL,
                followers     INTEGER,
                PRIMARY KEY (snapshot_date, platform)
            )
        """)


def log_post(pick, platform: str, post_id: str = None):
    """Record a successfully published pick."""
    _init()
    with _conn() as conn:
        conn.execute("""
            INSERT INTO posts (date, match, league, label, odds, confidence_pct, edge_pct, tier, platform, post_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date.today().isoformat(),
            pick.match,
            pick.league,
            pick.label,
            pick.odds,
            pick.confidence_pct,
            round(pick.edge * 100, 1),
            pick.tier,
            platform,
            post_id,
        ))


def set_result(match: str, post_date: str, result: str):
    """Set the outcome for a pick. result: 'win', 'loss', or 'void'."""
    _init()
    with _conn() as conn:
        conn.execute(
            "UPDATE posts SET result = ? WHERE match = ? AND date = ?",
            (result, match, post_date),
        )


def get_today() -> list[dict]:
    _init()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE date = ? ORDER BY created_at DESC",
            (date.today().isoformat(),),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent(days: int = 30) -> list[dict]:
    _init()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE date >= date('now', ?) ORDER BY created_at DESC",
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def weekly_summary() -> list[dict]:
    """Per-day, per-platform summary for the last 7 days."""
    _init()
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                date,
                platform,
                COUNT(*)                                                AS posted,
                SUM(CASE WHEN result = 'win'  THEN 1 ELSE 0 END)       AS wins,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END)       AS losses,
                ROUND(AVG(confidence_pct), 1)                          AS avg_confidence,
                ROUND(AVG(edge_pct), 1)                                AS avg_edge
            FROM posts
            WHERE date >= date('now', '-7 days')
            GROUP BY date, platform
            ORDER BY date DESC, platform
        """).fetchall()
    return [dict(r) for r in rows]


def earliest_post_date() -> str | None:
    """Return the earliest post date (YYYY-MM-DD) on record, or None if empty.

    Used as a fallback anchor for the "Day X" journey counter when
    EPIFANI_START_DATE is not configured.
    """
    _init()
    with _conn() as conn:
        row = conn.execute("SELECT MIN(date) AS first_date FROM posts").fetchone()
    return row["first_date"] if row and row["first_date"] else None


def total_stats() -> dict:
    """All-time totals."""
    _init()
    with _conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)                                          AS total_posted,
                COUNT(DISTINCT date)                              AS days_active,
                SUM(CASE WHEN result = 'win'  THEN 1 ELSE 0 END) AS total_wins,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS total_losses,
                ROUND(AVG(confidence_pct), 1)                    AS avg_confidence,
                ROUND(AVG(edge_pct), 1)                          AS avg_edge
            FROM posts
        """).fetchone()
    return dict(row)


# ── Social posts + metrics (Founder's Journey auto-posting) ─────────

def log_social_post(platform: str, post_id: str | None, url: str | None, meta: dict) -> None:
    """meta: day, kind, fam, hook, caption, voiceover (all optional)."""
    _init()
    with _conn() as conn:
        conn.execute("""
            INSERT INTO social_posts (date, day, kind, fam, hook, platform, post_id, url, caption, voiceover)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date.today().isoformat(), meta.get("day"), meta.get("kind"), meta.get("fam"),
              meta.get("hook"), platform, post_id, url, meta.get("caption"), meta.get("voiceover")))


def social_posts_since(days: int) -> list[dict]:
    _init()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM social_posts WHERE date >= date('now', ?) ORDER BY date, platform",
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def update_social_post(row_id: int, post_id: str, url: str | None) -> None:
    """Fill in the real id once known (TikTok inbox drafts get one only after you tap Post)."""
    _init()
    with _conn() as conn:
        conn.execute("UPDATE social_posts SET post_id = ?, url = ? WHERE id = ?", (post_id, url, row_id))


def save_post_metrics(snapshot_date: str, platform: str, post_id: str, m: dict) -> None:
    _init()
    with _conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO post_metrics
                (snapshot_date, platform, post_id, views, likes, comments, shares, saves, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_date, platform, post_id, m.get("views"), m.get("likes"), m.get("comments"),
              m.get("shares"), m.get("saves"), m.get("extra")))


def save_account_metrics(snapshot_date: str, platform: str, followers: int | None) -> None:
    _init()
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO account_metrics VALUES (?, ?, ?)",
                     (snapshot_date, platform, followers))


def post_metrics_on(snapshot_date: str) -> dict:
    """{(platform, post_id): metrics row} for one snapshot day."""
    _init()
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM post_metrics WHERE snapshot_date = ?",
                            (snapshot_date,)).fetchall()
    return {(r["platform"], r["post_id"]): dict(r) for r in rows}


def followers_on(snapshot_date: str) -> dict:
    """{platform: followers} for one snapshot day."""
    _init()
    with _conn() as conn:
        rows = conn.execute("SELECT platform, followers FROM account_metrics WHERE snapshot_date = ?",
                            (snapshot_date,)).fetchall()
    return {r["platform"]: r["followers"] for r in rows}
