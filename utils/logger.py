import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(level: str = "INFO", log_file: str = "./logs/bot.log", max_size_mb: int = 10, backup_count: int = 5) -> logging.Logger:
    """
    Configure structured logging with rotation and separate error log file.

    Format example:
    [2025-01-20 10:30:45] [INFO] Command: /analyze user_id=123456
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    error_log_file = os.path.join(os.path.dirname(log_file), "errors.log")

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Common formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (all logs)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_size_mb * 1024 * 1024, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Error file handler
    error_handler = RotatingFileHandler(
        error_log_file, maxBytes=max_size_mb * 1024 * 1024, backupCount=backup_count, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers if reconfigured
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console)

    # Reduce verbosity of noisy libraries
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    logger.info("Logger initialized")
    return logger
