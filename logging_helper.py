import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("log")
LOG_FILE = LOG_DIR / "bridge.log"


def setup_canonical_logging(logger_name: str = "teams_bridge") -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_level_str = os.getenv("BRIDGE_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    # Use __name__ from the caller, but attach it to the canonical hierarchy
    # Since the setup configures "teams_bridge", we can format the logger name
    # We strip any __main__ or keep it simple.
    name = f"teams_bridge.{module_name.split('.')[-1]}"
    return logging.getLogger(name)

def get_log_file_path() -> Path:
    return LOG_FILE
