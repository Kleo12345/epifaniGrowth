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
