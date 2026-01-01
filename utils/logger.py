from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name: str, log_dir: str) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = RotatingFileHandler(
            filename=os.path.join(log_dir, "engine.log"),
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger
