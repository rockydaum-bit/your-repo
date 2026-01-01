from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
import sqlite3

from config import EngineConfig
from utils.paths import EnginePaths

@contextmanager
def get_db_connection(cfg: EngineConfig, paths: EnginePaths) -> Iterator[sqlite3.Connection]:
    """Return a DB connection according to the configured driver.

    Today this supports SQLite only. Callers should use this context manager
    instead of opening sqlite3.connect(paths.db_path) directly. When moving to
    Postgres or another DB, update this function only.
    """
    driver = getattr(cfg, "db_driver", "sqlite")
    if driver in ("sqlite", "sqlite3"):
        con = sqlite3.connect(paths.db_path)
        try:
            con.row_factory = sqlite3.Row
            yield con
        finally:
            con.close()
    else:
        raise RuntimeError(f"Unsupported db driver: {driver}")
