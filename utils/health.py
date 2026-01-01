import os
import sqlite3
from utils.db import init_db
from utils.json_validate import save_json
from utils.db import SCHEMA_SQL
from datetime import datetime

def preflight_check(cfg, paths, mode="run", channel_id=None):
    """Perform role-aware preflight checks.

    For `brain` role we enforce OpenAI/YouTube presence when relevant.
    For `worker` role we require DB and storage but downgrade external API
    checks to warnings so workers can join with minimal config.
    """
    errors = []
    warnings = []
    # Engine root
    if not os.path.isdir(cfg.engine_root):
        errors.append(f"Engine root {cfg.engine_root} does not exist or is not a directory.")
    # Required dirs
    for d in [paths.data_dir, paths.state_dir, paths.logs_dir, paths.root, os.path.join(cfg.engine_root, "assets")]:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create/access required dir: {d} ({e})")
    # DB health
    db_path = paths.db_path
    try:
        if not os.path.exists(db_path):
            init_db(db_path)
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        # Check required tables
        required = ["videos", "prompt_assignments", "analytics_daily", "orchestrator_events", "costs"]
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = set(r[0] for r in cur.fetchall())
        for t in required:
            if t not in tables:
                errors.append(f"DB missing required table: {t}")
        con.close()
    except Exception as e:
        errors.append(f"DB error: {e}")
    # Config health (role-aware)
    role = getattr(cfg, "role", "brain")
    if mode in ("run", "measure", "score"):
        if role == "brain":
            if not getattr(cfg, "openai_api_key", None):
                errors.append("OpenAI API key missing in config.")
        else:
            # worker: warn but don't fail
            if not getattr(cfg, "openai_api_key", None):
                warnings.append("OpenAI API key not set (worker).")
    if mode == "run":
        yt = getattr(cfg, "youtube", None)
        if role == "brain":
            if not yt or not getattr(yt, "client_secrets_path", None) or not getattr(yt, "token_path", None):
                errors.append("YouTube client/token not configured for publish mode.")
        else:
            if not yt or not getattr(yt, "client_secrets_path", None) or not getattr(yt, "token_path", None):
                warnings.append("YouTube client/token not configured (worker).")
    # Budget/hardware (optional, soft fail)
    # ...
    if warnings:
        print("Preflight warnings:")
        for w in warnings:
            print(" -", w)

    if errors:
        # Write orchestrator_events row and alerts.json if possible
        ts = datetime.utcnow().isoformat() + "Z"
        try:
            from utils.db import insert_orchestrator_event
            insert_orchestrator_event(db_path, ts, "ERROR", "preflight_failed", {"errors": errors, "mode": mode, "channel_id": channel_id})
        except Exception:
            pass
        try:
            if channel_id:
                out_dir = os.path.join(cfg.engine_root, "assets", "channels", channel_id, "pipeline", "ops")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, "alerts.json")
                save_json(out_path, {"last_alert_ts": ts, "severity": "error", "source": mode, "message": "; ".join(errors), "run_id": None})
        except Exception:
            pass
        print("Preflight check failed:")
        for e in errors:
            print("  -", e)
        exit(2)
