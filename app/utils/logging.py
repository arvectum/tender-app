from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _ensure_log_dir() -> Path:
    settings = get_settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.logs_dir


def get_file_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logs_dir = _ensure_log_dir()
    file_handler = logging.FileHandler(logs_dir / filename, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
