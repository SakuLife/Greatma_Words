"""
Logging utilities for the application.
GitHub Actions環境ではアノテーション形式 (::group::, ::error:: 等) を自動適用。
"""

import logging
import os
import sys
from pathlib import Path

from app.config import settings


def _is_github_actions() -> bool:
    """GitHub Actions環境かどうかを判定する。"""
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _get_utf8_stream():
    """
    Try to open stdout in UTF-8 to avoid cp932/shift_jis mojibake on Windows consoles.
    Falls back to the original stdout if it fails.
    """
    try:
        return open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
    except Exception:
        return sys.stdout


class GitHubActionsFormatter(logging.Formatter):
    """GitHub Actions用のログフォーマッタ。エラー/警告をアノテーションとして出力する。"""

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if record.levelno >= logging.ERROR:
            return f"::error::{msg}"
        elif record.levelno >= logging.WARNING:
            return f"::warning::{msg}"
        elif record.levelno <= logging.DEBUG:
            return f"::debug::{msg}"
        else:
            return msg


def setup_logger(name: str = "greatman_words", log_file: Path | None = None) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.
    GitHub Actions環境ではアノテーション形式を使用する。

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

    # GitHub Actionsではアノテーション形式、それ以外は通常形式
    if _is_github_actions():
        console_handler.setFormatter(GitHubActionsFormatter())
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File handler (optional, always use standard format)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def log_group(title: str) -> None:
    """GitHub Actionsのログをグループ化（折りたたみ可能にする）。"""
    if _is_github_actions():
        print(f"::group::{title}", flush=True)
    else:
        logger.info("=" * 60)
        logger.info(title)
        logger.info("=" * 60)


def log_group_end() -> None:
    """GitHub Actionsのロググループを閉じる。"""
    if _is_github_actions():
        print("::endgroup::", flush=True)


# Default logger instance
logger = setup_logger()
