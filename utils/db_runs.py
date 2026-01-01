import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Iterator

from config import EngineConfig
from utils.paths import EnginePaths
from utils.db_conn import get_db_connection


@contextmanager
def _run_connection(
    db_path: Optional[str],
    cfg: Optional[EngineConfig],
    paths: Optional[EnginePaths],
) -> Iterator["sqlite3.Connection"]:
    """
    Internal helper to obtain a connection either from cfg/paths (preferred)
    or directly from db_path (legacy). Keeps callers compatible.
    """
    if cfg is not None and paths is not None:
        # Preferred: use central DB connection helper (sqlite/Postgres later).
        with get_db_connection(cfg, paths) as con:
            yield con
        return

    if db_path is None:
        raise ValueError("db_path or (cfg and paths) must be provided")

    # Legacy: direct sqlite3 connection
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        yield con
    finally:
        con.close()


def insert_run_start(
    db_path: Optional[str] = None,
    *,
    cfg: Optional[EngineConfig] = None,
    paths: Optional[EnginePaths] = None,
    run_id: Optional[str] = None,
    channel_id: str,
    mode: str,
    status: str = "started",
    command: Optional[str] = None,
    meta: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> str:
    """
    Insert a run-start record.

    Preferred usage: cfg+paths; legacy: db_path positional. If `run_id`
    is not provided, one will be generated and returned.
    """
    from uuid import uuid4
    from datetime import datetime, timezone
    import json

    if run_id is None:
        run_id = str(uuid4())

    ts_now = datetime.now(timezone.utc).isoformat()

    with _run_connection(db_path, cfg, paths) as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO runs (run_id, channel_id, mode, ts_start, ts_end, command, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO NOTHING
            """,
            (run_id, channel_id, mode, ts_now, None, json.dumps(meta or {}) if meta is not None else command, status, error_message),
        )
        con.commit()

    return run_id


def update_run_end(
    db_path: Optional[str] = None,
    *,
    cfg: Optional[EngineConfig] = None,
    paths: Optional[EnginePaths] = None,
    run_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    from datetime import datetime, timezone

    ts_now = datetime.now(timezone.utc).isoformat()

    with _run_connection(db_path, cfg, paths) as con:
        cur = con.cursor()
        cur.execute(
            """
            UPDATE runs
            SET status = ?, error_message = ?, ts_end = ?
            WHERE run_id = ?
            """,
            (status, error_message, ts_now, run_id),
        )
        con.commit()


def list_recent_runs(
    db_path: Optional[str] = None,
    *,
    cfg: Optional[EngineConfig] = None,
    paths: Optional[EnginePaths] = None,
    channel_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    with _run_connection(db_path, cfg, paths) as con:
        cur = con.cursor()
        params: list[object] = []
        sql = """
            SELECT run_id, channel_id, mode, status, ts_start, ts_end, error_message
            FROM runs
        """
        where_clauses = []
        if channel_id:
            where_clauses.append("channel_id = ?")
            params.append(channel_id)
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += " ORDER BY ts_start DESC LIMIT ?"
        params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "run_id": r[0],
                "channel_id": r[1],
                "mode": r[2],
                "status": r[3],
                "ts_start": r[4],
                "ts_end": r[5],
                "error_message": r[6],
            }
        )
    return out


# Backwards-compatible alias for previous name
def fetch_recent_runs(db_path: Optional[str], channel_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    return list_recent_runs(db_path, channel_id=channel_id, limit=limit)
