from fastapi import FastAPI, HTTPException, Query
from typing import Optional
import os
import json
from config import get_config
from utils.paths import EnginePaths
from utils.ops_status import generate_channel_status
from utils.db import fetch_recent_alerts, list_video_publications
from utils.ops_status import get_worker_status
from utils.db_runs import fetch_recent_runs
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import sys

app = FastAPI(title="Text Autonomous Media Engine API")

cfg = get_config()
paths = EnginePaths(cfg.engine_root)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


BASE_DIR = _base_dir()
UI_DIST = BASE_DIR / "ui_dist"

# fallback to repo ui/dist or engine_root/ui_dist
if not UI_DIST.exists():
    alt = Path(cfg.engine_root) / "ui_dist"
    if alt.exists():
        UI_DIST = alt
    else:
        alt2 = Path(cfg.engine_root) / "ui" / "dist"
        if alt2.exists():
            UI_DIST = alt2
# UI static serving is attached below after API routes are defined to
# ensure API endpoints are registered before the SPA catch-all.

# Utility: List all channel directories under assets/channels


def list_channels():
    channels_root = os.path.join(cfg.engine_root, "assets", "channels")
    if not os.path.isdir(channels_root):
        return []
    return [
        d
        for d in os.listdir(channels_root)
        if os.path.isdir(os.path.join(channels_root, d))
    ]


@app.get("/api/channels")
def get_channels():
    channels = list_channels()
    # normalize and dedupe by channel_id while preserving order
    seen: set[str] = set()
    result = []
    for channel_id in channels:
        if channel_id in seen:
            continue
        seen.add(channel_id)
        status = generate_channel_status(cfg, paths, channel_id)
        result.append(
            {
                "channel_id": channel_id,
                "name": channel_id,  # Placeholder for future friendly name
                "overall_status": status.get("overall_status", "unknown"),
            }
        )
    return result


@app.get("/api/channels/{channel_id}/status")
def get_channel_status(channel_id: str):
    try:
        status = generate_channel_status(cfg, paths, channel_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Channel not found or error: {e}")


@app.get("/api/channels/{channel_id}/alerts")
def get_channel_alerts(
    channel_id: str, severity: Optional[str] = Query(None), limit: int = 50
):
    # severity: "info" | "warning" | "error" (optional)
    alerts = fetch_recent_alerts(paths.db_path, channel_id=channel_id, limit=limit)
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    # Parse meta_json to meta dict
    for a in alerts:
        if a.get("meta_json"):
            try:
                a["meta"] = json.loads(a["meta_json"])
            except Exception:
                a["meta"] = None
        else:
            a["meta"] = None
        a.pop("meta_json", None)
    return alerts


@app.get("/api/channels/{channel_id}/runs")
def get_channel_runs(channel_id: str, limit: int = 50):
    runs = fetch_recent_runs(paths.db_path, channel_id=channel_id, limit=limit)
    return runs


@app.get("/api/channels/{channel_id}/publications")
def get_channel_publications(channel_id: str, limit: int = 50):
    try:
        rows = list_video_publications(
            paths.db_path, channel_id=channel_id, limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [
        {
            "channel_id": r.get("channel_id"),
            "video_id": r.get("video_id"),
            "platform": r.get("platform"),
            "external_video_id": r.get("platform_video_id"),
            "published_ts": r.get("published_ts"),
            "status": r.get("status"),
        }
        for r in rows
    ]


@app.get("/api/workers")
def list_workers():
    try:
        workers = get_worker_status(cfg, paths)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    # normalize keys for the UI
    return [
        {
            "worker_id": w.get("worker_id") or w.get("channel_id"),
            "last_heartbeat": w.get("last_heartbeat"),
            "last_status": w.get("last_status"),
        }
        for w in workers
    ]


@app.get("/api/version")
def get_version():
    # Return basic runtime info from config for diagnostics and UI
    return {
        "version": cfg.version,
        "role": cfg.role,
        "mode": cfg.mode,
        "db_driver": cfg.db_driver,
        "storage_mode": cfg.storage_mode,
        "engine_root": cfg.engine_root,
        "worker_id": getattr(cfg, "worker_id", None),
    }


# Attach UI static routes after API endpoints so API paths are matched first.
if UI_DIST.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIST), html=False), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_ui_root():
        index = UI_DIST / "index.html"
        return FileResponse(index)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = UI_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not Found")
