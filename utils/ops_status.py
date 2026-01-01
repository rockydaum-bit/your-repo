import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from utils.json_validate import save_json
from utils.alerts import get_recent_alerts
from utils.db_conn import get_db_connection
def _compute_overall_status(latest_alerts: list[dict[str, Any]]) -> str:
    """
    Map recent alerts to a coarse health status.
    Priority: error > warning > ok.
    """
    severities = {a["severity"] if isinstance(a, dict) else a.severity for a in latest_alerts}
    if "error" in severities:
        return "failing"
    if "warning" in severities:
        return "degraded"
    return "ok"

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_channel_status(cfg, paths, channel_id: str) -> Dict[str, Any]:
    db_path = paths.db_path
    status: Dict[str, Any] = {
        "ts": _utc_now_iso(),
        "channel_id": channel_id,
        "engine_root": cfg.engine_root,
        "feature_flags": {
            "enable_auto_promote": bool(getattr(cfg, "enable_auto_promote", False)),
            "auto_promote_min_videos": int(getattr(cfg, "auto_promote_min_videos", 6)),
            "auto_promote_min_days": int(getattr(cfg, "auto_promote_min_days", 7)),
        },
        "publish": {},
        "events": {},
        "ab": {},
    }

    # Use centralized DB connection helper so the driver can change later.
    with get_db_connection(cfg, paths) as con:
        con.row_factory = __import__("sqlite3").Row

        # Publish stats
        row = con.execute(
        """
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) as published,
          SUM(CASE WHEN status='upload_failed' THEN 1 ELSE 0 END) as upload_failed
        FROM videos
        WHERE channel_id = ?
        """,
        (channel_id,),
    ).fetchone()
        status["publish"] = dict(row) if row else {}

        # Last published video
        row2 = con.execute(
        """
        SELECT video_id, run_id, youtube_video_id, published_ts, status
        FROM videos
        WHERE channel_id = ?
        ORDER BY published_ts DESC
        LIMIT 1
        """,
        (channel_id,),
    ).fetchone()
        status["publish"]["last"] = dict(row2) if row2 else None

        # Recent events
        rows = con.execute(
            """
            SELECT ts, level, event, payload_json
            FROM orchestrator_events
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()
        status["events"]["tail_20"] = [dict(r) for r in rows]

        # Alerts (alerts module still accepts db_path)
        alerts_objs = get_recent_alerts(db_path, channel_id=channel_id, limit=20)
        latest_alerts = [
            {
                "id": a.id,
                "ts": a.ts,
                "severity": a.severity,
                "code": a.code,
                "message": a.message,
                "run_id": a.run_id,
                "meta": a.meta,
            }
            for a in alerts_objs
        ]
        status["latest_alerts"] = latest_alerts
        status["overall_status"] = _compute_overall_status(latest_alerts)

    # Write channel-scoped artifact
    out_dir = os.path.join(cfg.engine_root, "assets", "channels", channel_id, "pipeline", "ops")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "status.json")
    save_json(out_path, status)

    return {"status_path": out_path, "status": status}


def get_worker_status(cfg, paths) -> List[Dict[str, Any]]:
    """
    Returns one row per worker (stored as channel_id for heartbeats) with last heartbeat and last status.
    Uses runs where mode = 'worker_heartbeat' and groups by channel_id.
    """
    with get_db_connection(cfg, paths) as con:
        con.row_factory = __import__("sqlite3").Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT
              channel_id AS worker_id,
              MAX(ts_end) AS last_heartbeat,
              MAX(status) AS last_status
            FROM runs
            WHERE mode = 'worker_heartbeat'
            GROUP BY channel_id
            ORDER BY last_heartbeat DESC
            """,
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
