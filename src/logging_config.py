"""Central logging setup with console and rotating file handlers."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.config import LOG_DIR


def setup_logging(level: str = "INFO") -> None:
    """Configure package logging once at application startup."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger("src")
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        LOG_DIR / "crawler.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    error_handler = RotatingFileHandler(
        LOG_DIR / "error_log.txt",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
