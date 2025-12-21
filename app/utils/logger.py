"""
Logging utilities for the application.
"""

import logging
import sys
from pathlib import Path

from app.config import settings


def _get_utf8_stream():
    """
    Try to open stdout in UTF-8 to avoid cp932/shift_jis mojibake on Windows consoles.
    Falls back to the original stdout if it fails.
    """
    try:
        return open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
    except Exception:
        return sys.stdout


def setup_logger(name: str = "greatman_words", log_file: Path | None = None) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    Args:
        name: Logger name
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set level based on debug setting
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Console handler (try UTF-8 stream to prevent mojibake on Windows)
    console_stream = _get_utf8_stream()
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger instance
logger = setup_logger()
