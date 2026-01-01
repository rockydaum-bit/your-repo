from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.db import insert_alert, fetch_recent_alerts


@dataclass(frozen=True)
class Alert:
    id: int
    ts: str
    severity: str
    code: str
    channel_id: Optional[str]
    run_id: Optional[str]
    message: str
    meta: Optional[Dict[str, Any]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def raise_alert(
    db_path: str,
    *,
    channel_id: Optional[str],
    run_id: Optional[str],
    severity: str,
    code: str,
    message: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    High-level alert emitter.
    Use this from health checks, CLI commands, publishing, etc.
    """
    if severity not in ("info", "warning", "error"):
        severity = "error"
    ts = _utc_now_iso()
    meta_json = json.dumps(meta) if meta is not None else None
    insert_alert(
        db_path=db_path,
        ts=ts,
        severity=severity,
        code=code,
        channel_id=channel_id,
        run_id=run_id,
        message=message,
        meta_json=meta_json,
    )


def get_recent_alerts(
    db_path: str,
    channel_id: Optional[str] = None,
    limit: int = 50,
) -> List[Alert]:
    """
    Return most recent alerts (global or per-channel) as Alert objects.
    """
    rows = fetch_recent_alerts(db_path, channel_id=channel_id, limit=limit)
    alerts: List[Alert] = []
    for row in rows:
        meta: Optional[Dict[str, Any]] = None
        raw_meta = row.get("meta_json")
        if raw_meta:
            try:
                meta = json.loads(raw_meta)
            except json.JSONDecodeError:
                meta = None
        alerts.append(
            Alert(
                id=row["id"],
                ts=row["ts"],
                severity=row["severity"],
                code=row["code"],
                channel_id=row.get("channel_id"),
                run_id=row.get("run_id"),
                message=row["message"],
                meta=meta,
            )
        )
    return alerts
