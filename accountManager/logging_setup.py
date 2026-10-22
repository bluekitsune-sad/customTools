"""Central logging setup for Chrome Account Manager.

Logs are local, rotated, and deliberately exclude secrets. Never pass
passwords, CSRF tokens, vault contents, notes, bookmark titles, or bookmark
URLs to a logger.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "cam"
LOG_FILE_NAME = "app.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def get_logger(name: str) -> logging.Logger:
    """Return a child logger such as ``cam.scanner``."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logging(
    base_dir: str | Path, level: int = logging.INFO
) -> Path | None:
    """Configure console and rotating-file logging.

    Returns the active log file path, or ``None`` when file logging could not
    be enabled (console logging still works).
    """
    log_dir = Path(base_dir).resolve() / "logs"
    log_path = log_dir / LOG_FILE_NAME
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return log_path

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_path: Path | None = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
        file_path = log_path
    except OSError as exc:
        print(f"[warn] File logging is unavailable: {exc}", file=sys.stderr)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    return file_path
