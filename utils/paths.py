from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import load_config, EngineConfig

@dataclass(frozen=True)
class EnginePaths:
    root: str

    @property
    def data_dir(self) -> str:
        return resolve_path_from_root(self.root, "data")

    @property
    def logs_dir(self) -> str:
        return os.path.join(self.data_dir, "logs")

    @property
    def db_path(self) -> str:
        return resolve_path_from_root(self.root, os.path.join("data", "revenue.db"))

    @property
    def state_dir(self) -> str:
        return os.path.join(self.data_dir, "state")

    @property
    def prompts_dir(self) -> str:
        return resolve_path_from_root(self.root, "prompts")

    def prompt_path(self, rel: str) -> str:
        return os.path.join(self.prompts_dir, rel)

    def ensure_dirs(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.state_dir, exist_ok=True)


def resolve_path(cfg_or_root: Optional[EngineConfig | str], rel_path: str) -> str:
    """
    Resolve a logical relative path according to storage settings.

    - If passed an EngineConfig, use storage_mode/nas_root/local_root settings.
    - If passed a root string, behave like previous join on that root.
    """
    if isinstance(cfg_or_root, str) or cfg_or_root is None:
        root = cfg_or_root or "."
        return str(Path(root) / rel_path)

    cfg: EngineConfig = cfg_or_root
    # local by default
    if getattr(cfg, "storage_mode", "local") == "nas" and cfg.nas_root:
        base = cfg.nas_root
    else:
        base = getattr(cfg, "local_root", None) or getattr(cfg, "engine_root", ".")
    return str(Path(base) / rel_path)


def resolve_path_from_root(root: str, rel_path: str) -> str:
    """
    Transitional helper that resolves relative paths against a root string.
    Keep this while gradually switching callers to resolve_path(cfg, ...).
    """
    return str(Path(root) / rel_path)
