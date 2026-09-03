from __future__ import annotations

import logging
import logging.config
import os
import sys
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / ".fusion-health"


def _log_dir() -> Path:
    return Path(os.getenv("FUSION_HEALTH_LOG_DIR", str(DEFAULT_LOG_DIR)))


def configure_logging(level: str | None = None) -> None:
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    level = level or os.getenv("FUSION_HEALTH_LOG_LEVEL", "INFO").upper()
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "format": '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
            },
            "plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
                "formatter": "plain",
                "level": level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_dir / "app.log"),
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "formatter": "json",
                "level": "DEBUG",
                "encoding": "utf-8",
            },
        },
        "root": {"handlers": ["console", "file"], "level": level},
        "loggers": {
            "fusion_health": {"level": level, "propagate": True},
            "uvicorn": {"level": "INFO"},
        },
    }
    logging.config.dictConfig(config)
    logging.getLogger(__name__).info("logging configured: level=%s, dir=%s", level, log_dir)
