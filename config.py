"""
Centralized configuration loader.

Supports defaults, YAML file (config/engine.yaml) and environment variable overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import socket

from dotenv import load_dotenv
import yaml

load_dotenv()


@dataclass(frozen=True)
class BudgetPolicy:
    monthly_cap_usd: float = 150.0
    openai_cap_usd: float = 80.0
    elevenlabs_cap_usd: float = 50.0
    stop_at_pct: float = 0.85  # stop at 85% of caps


@dataclass(frozen=True)
class HardwarePolicy:
    cpu_pause_pct: float = 85.0
    gpu_vram_pause_pct: float = 90.0
    disk_free_pause_pct: float = 10.0


@dataclass(frozen=True)
class YouTubePolicy:
    client_secrets_path: str
    token_path: str
    privacy_status_default: str = "private"


@dataclass(frozen=True)
class ElevenLabsPolicy:
    api_key: str
    default_voice_id: str
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"
    stability: float = 0.35
    similarity_boost: float = 0.80
    style: float = 0.20
    speaker_boost: bool = True


@dataclass
class EngineConfig:
    engine_root: str = "."
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    timezone: str = "America/New_York"
    budget: BudgetPolicy = BudgetPolicy()
    hardware: HardwarePolicy = HardwarePolicy()
    youtube: Optional[YouTubePolicy] = None
    elevenlabs: Optional[ElevenLabsPolicy] = None
    enable_auto_promote: bool = False
    auto_promote_min_videos: int = 6
    auto_promote_min_days: int = 7
    scoring_window_days: int = 7
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    channels: List[Dict[str, Any]] | None = None
    # infra and storage
    db_driver: str = "sqlite"
    db_url: str = "data/revenue.db"
    storage_mode: str = "local"
    local_root: str = "."
    nas_root: Optional[str] = None
    object_base_url: Optional[str] = None
    # cluster/role
    mode: str = "local"
    role: str = "brain"
    version: str = "0.0.0-local"
    worker_id: Optional[str] = None


DEFAULT_CONFIG_PATH = Path("config") / "engine.yaml"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config(config_path: Optional[str] = None) -> EngineConfig:
    """
    Load EngineConfig from YAML + env overrides.

    Precedence: defaults < file < env
    """
    base = {
        "engine_root": ".",
        "server": {"host": "127.0.0.1", "port": 8000},
        "ab_testing": {
            "enable_auto_promote": False,
            "auto_promote_min_videos": 6,
            "auto_promote_min_days": 7,
            "scoring_window_days": 7,
        },
        "channels": [],
        "db": {"driver": "sqlite", "url": "data/revenue.db"},
        "storage": {"mode": "local", "local_root": ".", "nas_root": None, "object_base_url": None},
        "mode": "local",
        "role": "brain",
        "version": "0.0.0-local",
    }

    # Allow overriding the config file via env var ENGINE_CONFIG_PATH, then function arg, else default
    env_cfg = os.getenv("ENGINE_CONFIG_PATH")
    if env_cfg:
        cfg_path = Path(env_cfg)
    else:
        cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if cfg_path.is_file():
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                file_cfg = yaml.safe_load(f) or {}
            for k, v in file_cfg.items():
                if isinstance(v, dict) and isinstance(base.get(k), dict):
                    base[k].update(v)
                else:
                    base[k] = v
        except Exception:
            # fallback to defaults on parse error
            file_cfg = {}

    # Env overrides and legacy env handling
    engine_root = os.getenv("ENGINE_ROOT", base.get("engine_root", ".")) or "."

    # OpenAI key: prefer env, then YAML file
    openai_api_key = os.getenv("OPENAI_API_KEY") or base.get("openai_api_key") or None
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")

    # YouTube: prefer env paths, then YAML config
    yt_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS_PATH")
    yt_token = os.getenv("YOUTUBE_TOKEN_PATH")
    youtube = None
    if yt_secrets and yt_token:
        youtube = YouTubePolicy(client_secrets_path=yt_secrets, token_path=yt_token)
    else:
        yt_cfg = base.get("youtube") or {}
        if yt_cfg and yt_cfg.get("client_secrets_path") and yt_cfg.get("token_path"):
            youtube = YouTubePolicy(client_secrets_path=yt_cfg.get("client_secrets_path"), token_path=yt_cfg.get("token_path"))

    # ElevenLabs
    el_key = os.getenv("ELEVENLABS_API_KEY")
    el_voice = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID")
    el_model = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    eleven = None
    if el_key and el_voice:
        eleven = ElevenLabsPolicy(api_key=el_key, default_voice_id=el_voice, model_id=el_model)

    enable_auto_promote = _bool_env("ENABLE_AUTO_PROMOTE", base["ab_testing"]["enable_auto_promote"])
    auto_promote_min_videos = int(os.getenv("AUTO_PROMOTE_MIN_VIDEOS", base["ab_testing"]["auto_promote_min_videos"]))
    auto_promote_min_days = int(os.getenv("AUTO_PROMOTE_MIN_DAYS", base["ab_testing"]["auto_promote_min_days"]))

    server_host = os.getenv("SERVER_HOST", base["server"]["host"]) or "127.0.0.1"
    server_port = int(os.getenv("SERVER_PORT", base["server"]["port"]))

    # DB
    db_cfg = base.get("db", {})
    db_driver = os.getenv("DB_DRIVER", db_cfg.get("driver", "sqlite"))
    db_url = os.getenv("DB_URL", db_cfg.get("url", "data/revenue.db"))

    # Storage
    storage_cfg = base.get("storage", {})
    storage_mode = os.getenv("STORAGE_MODE", storage_cfg.get("mode", "local"))
    local_root = os.getenv("LOCAL_ROOT", storage_cfg.get("local_root", engine_root))
    nas_root = os.getenv("NAS_ROOT", storage_cfg.get("nas_root"))
    object_base_url = os.getenv("OBJECT_BASE_URL", storage_cfg.get("object_base_url"))

    mode = os.getenv("MODE", base.get("mode", "local"))
    # Prefer ENGINE_ROLE, fall back to legacy ROLE env, then YAML
    role = os.getenv("ENGINE_ROLE") or os.getenv("ROLE") or base.get("role", "brain")
    version = os.getenv("VERSION", base.get("version", "0.0.0-local"))

    # Worker id precedence: env > YAML.file worker.id or worker_id > hostname
    env_worker = os.getenv("WORKER_ID")
    file_worker = base.get("worker_id") or (base.get("worker") or {}).get("id")
    if env_worker:
        worker_id = env_worker
    elif file_worker:
        worker_id = str(file_worker)
    else:
        try:
            worker_id = socket.gethostname()
        except Exception:
            worker_id = None

    channels = base.get("channels") or []

    return EngineConfig(
        engine_root=str(engine_root),
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        youtube=youtube,
        elevenlabs=eleven,
        enable_auto_promote=enable_auto_promote,
        auto_promote_min_videos=auto_promote_min_videos,
        auto_promote_min_days=auto_promote_min_days,
        scoring_window_days=base["ab_testing"].get("scoring_window_days", 7),
        server_host=server_host,
        server_port=server_port,
        channels=channels,
        db_driver=db_driver,
        db_url=str(db_url),
        storage_mode=storage_mode,
        local_root=str(local_root),
        nas_root=nas_root,
        object_base_url=object_base_url,
        mode=mode,
        role=role,
        version=version,
        worker_id=worker_id,
    )


def get_config() -> EngineConfig:
    return load_config()


def get_config_from_path(config_path: str | None) -> EngineConfig:
    """Load config from a specific path (or fallback to env/defaults).

    Use this from CLIs when a user passes `--config` to override the
    environment variable or default config path.
    """
    if config_path:
        return load_config(config_path)
    return load_config()
