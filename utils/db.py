from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Any, Dict, List, Optional
import json


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    vendor TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    run_id TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    topic TEXT,
    published_ts TEXT,
    youtube_video_id TEXT,
    status TEXT NOT NULL DEFAULT 'planned'
);

CREATE TABLE IF NOT EXISTS video_publications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_video_id TEXT,
    run_id TEXT,
    published_ts TEXT,
    status TEXT NOT NULL DEFAULT 'published',
    metadata_json TEXT,
    UNIQUE(channel_id, video_id, platform)
);

CREATE TABLE IF NOT EXISTS analytics_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    video_id TEXT,
    views REAL,
    watch_time_hours REAL,
    ctr REAL,
    avg_view_duration_sec REAL,
    rpm REAL,
    subs_net REAL,
    revenue_usd REAL
);

CREATE TABLE IF NOT EXISTS orchestrator_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    payload_json TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        severity TEXT NOT NULL,
        code TEXT NOT NULL,
        channel_id TEXT,
        run_id TEXT,
        message TEXT NOT NULL,
        meta_json TEXT
);
"""

# --- Alerts Helpers ---


def insert_alert(
    db_path: str,
    *,
    ts: str,
    severity: str,
    code: str,
    channel_id: Optional[str],
    run_id: Optional[str],
    message: str,
    meta_json: Optional[str],
) -> None:
    from utils.db import connect  # avoid circulars if any

    with connect(db_path) as con:
        con.execute(
            "INSERT INTO alerts (ts, severity, code, channel_id, run_id, message, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, severity, code, channel_id, run_id, message, meta_json),
        )


def fetch_recent_alerts(
    db_path: str,
    *,
    channel_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    from utils.db import connect  # avoid circulars if any
    import sqlite3

    with connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        if channel_id is not None:
            cur.execute(
                "SELECT id, ts, severity, code, channel_id, run_id, message, meta_json FROM alerts WHERE channel_id = ? ORDER BY ts DESC, id DESC LIMIT ?",
                (channel_id, limit),
            )
        else:
            cur.execute(
                "SELECT id, ts, severity, code, channel_id, run_id, message, meta_json FROM alerts ORDER BY ts DESC, id DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


SCHEMA_SQL += """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    ts_start TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ts_end TEXT,
    command TEXT,
    status TEXT NOT NULL DEFAULT 'started',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS prompt_assignments (
    ts TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    arm TEXT NOT NULL,
    variant_manifest_rel TEXT,
    notes TEXT,
    PRIMARY KEY (channel_id, video_id)
);
"""


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as con:
        con.executescript(SCHEMA_SQL)


def insert_cost(
    db_path: str,
    ts: str,
    vendor: str,
    category: str,
    amount_usd: float,
    run_id: str | None = None,
    notes: str | None = None,
) -> None:
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO costs (ts, vendor, category, amount_usd, run_id, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, vendor, category, amount_usd, run_id, notes),
        )


def sum_costs_month(db_path: str, month_prefix: str) -> float:
    # month_prefix like "2025-12"
    with connect(db_path) as con:
        row = con.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) AS total FROM costs WHERE ts LIKE ?",
            (f"{month_prefix}%",),
        ).fetchone()
        return float(row["total"]) if row else 0.0


def log_event(
    db_path: str, ts: str, level: str, event: str, payload_json: str = "{}"
) -> None:
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO orchestrator_events (ts, level, event, payload_json) VALUES (?, ?, ?, ?)",
            (ts, level, event, payload_json),
        )


def insert_orchestrator_event(
    db_path: str,
    ts: str,
    level: str,
    event: str,
    payload: dict | None = None,
) -> None:
    with connect(db_path) as con:
        con.execute(
            """
            INSERT INTO orchestrator_events (ts, level, event, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                ts,
                level,
                event,
                json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False),
            ),
        )


def insert_analytics_daily(
    db_path: str,
    ts: str,
    channel_id: str,
    video_id: str | None,
    views: float | None,
    watch_time_hours: float | None,
    ctr: float | None,
    avg_view_duration_sec: float | None,
    rpm: float | None,
    subs_net: float | None,
    revenue_usd: float | None,
) -> None:
    with connect(db_path) as con:
        con.execute(
            """
            INSERT INTO analytics_daily
            (ts, channel_id, video_id, views, watch_time_hours, ctr, avg_view_duration_sec, rpm, subs_net, revenue_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                channel_id,
                video_id,
                views,
                watch_time_hours,
                ctr,
                avg_view_duration_sec,
                rpm,
                subs_net,
                revenue_usd,
            ),
        )


def list_recent_videos(db_path: str, channel_id: str, limit: int = 50) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            """
            SELECT channel_id, video_id, youtube_video_id, published_ts, status
            FROM videos
            WHERE channel_id = ?
            ORDER BY COALESCE(published_ts, '') DESC, id DESC
            LIMIT ?
            """,
            (channel_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def list_prompt_assignments_for_manifest(
    db_path: str, channel_id: str, variant_manifest_rel: str
) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            """
            SELECT video_id, arm, variant_manifest_rel, ts
            FROM prompt_assignments
            WHERE channel_id = ? AND variant_manifest_rel = ?
            ORDER BY ts ASC
            """,
            (channel_id, variant_manifest_rel),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Run Ledger Helpers ---
def insert_run_start(db_path: str, run_id: str, channel_id: str, mode: str) -> None:
    """Legacy-compatible wrapper that funnels to utils.db_runs.insert_run_start.

    Keeps the original signature so existing callsites/tests continue to work
    while the new implementation uses the centralized DB connection helper.
    """
    from utils import db_runs

    # pass through to new hybrid helper; preserve provided run_id
    db_runs.insert_run_start(db_path, run_id=run_id, channel_id=channel_id, mode=mode)


def update_run_end(
    db_path: str, run_id: str, status: str, error_message: str | None = None
) -> None:
    """Legacy-compatible wrapper that funnels to utils.db_runs.update_run_end.

    Preserves the original signature for backward compatibility.
    """
    from utils import db_runs

    db_runs.update_run_end(
        db_path, run_id=run_id, status=status, error_message=error_message
    )


def upsert_video_publish(
    db_path: str,
    channel_id: str,
    video_id: str,
    run_id: str,
    youtube_video_id: str,
    published_ts: str,
    status: str = "published",
) -> None:
    """
    Bind an upload result to videos table deterministically.
    UPDATE first; INSERT if absent. Idempotent on (channel_id, video_id).
    """
    with connect(db_path) as con:
        cur = con.execute(
            """
            UPDATE videos
            SET youtube_video_id = ?, published_ts = ?, status = ?, run_id = ?
            WHERE channel_id = ? AND video_id = ?
            """,
            (youtube_video_id, published_ts, status, run_id, channel_id, video_id),
        )
        if cur.rowcount and cur.rowcount > 0:
            return

        con.execute(
            """
            INSERT INTO videos (channel_id, video_id, run_id, topic, published_ts, youtube_video_id, status)
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            """,
            (channel_id, video_id, run_id, published_ts, youtube_video_id, status),
        )


def upsert_video_publication(
    db_path: str,
    channel_id: str,
    video_id: str,
    platform: str,
    platform_video_id: str | None,
    run_id: str | None,
    published_ts: str | None,
    status: str = "published",
    metadata: dict | None = None,
) -> None:
    """
    Record a publication to a platform. Idempotent on (channel_id, video_id, platform).
    Updates existing record if present, otherwise inserts.
    """
    meta_json = json.dumps(metadata or {}, separators=(",", ":"), ensure_ascii=False)
    with connect(db_path) as con:
        cur = con.execute(
            """
            UPDATE video_publications
            SET platform_video_id = ?, run_id = ?, published_ts = ?, status = ?, metadata_json = ?
            WHERE channel_id = ? AND video_id = ? AND platform = ?
            """,
            (
                platform_video_id,
                run_id,
                published_ts,
                status,
                meta_json,
                channel_id,
                video_id,
                platform,
            ),
        )
        if cur.rowcount and cur.rowcount > 0:
            return

        con.execute(
            """
            INSERT INTO video_publications
            (channel_id, video_id, platform, platform_video_id, run_id, published_ts, status, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                channel_id,
                video_id,
                platform,
                platform_video_id,
                run_id,
                published_ts,
                status,
                meta_json,
            ),
        )


def list_video_publications(
    db_path: str, channel_id: str, limit: int = 50
) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            """
            SELECT channel_id, video_id, platform, platform_video_id, run_id, published_ts, status, metadata_json
            FROM video_publications
            WHERE channel_id = ?
            ORDER BY COALESCE(published_ts, '') DESC, id DESC
            LIMIT ?
            """,
            (channel_id, limit),
        ).fetchall()
        results = [dict(r) for r in rows]
        for r in results:
            if r.get("metadata_json"):
                try:
                    r["metadata"] = json.loads(r.pop("metadata_json"))
                except Exception:
                    r["metadata"] = None
            else:
                r["metadata"] = None
        return results


def get_prompt_assignment(db_path: str, channel_id: str, video_id: str) -> str | None:
    with connect(db_path) as con:
        row = con.execute(
            "SELECT arm FROM prompt_assignments WHERE channel_id = ? AND video_id = ?",
            (channel_id, video_id),
        ).fetchone()
        return str(row["arm"]) if row else None


def upsert_prompt_assignment(
    db_path: str,
    ts: str,
    channel_id: str,
    video_id: str,
    arm: str,
    variant_manifest_rel: str | None = None,
    notes: str | None = None,
) -> None:
    with connect(db_path) as con:
        con.execute(
            """
            INSERT INTO prompt_assignments (ts, channel_id, video_id, arm, variant_manifest_rel, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id, video_id) DO UPDATE SET
              ts=excluded.ts,
              arm=excluded.arm,
              variant_manifest_rel=excluded.variant_manifest_rel,
              notes=excluded.notes
            """,
            (ts, channel_id, video_id, arm, variant_manifest_rel, notes),
        )
