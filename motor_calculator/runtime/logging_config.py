"""Restrained local-only application logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import RuntimePaths, create_runtime_directories, resolve_runtime_paths


LOGGER_NAME = "motor_calculator"


def initialize_local_logging(paths: RuntimePaths | None = None) -> logging.Logger:
    """Initialize a size-controlled local log with no telemetry or network sink."""

    runtime_paths = create_runtime_directories(paths or resolve_runtime_paths())
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    target = runtime_paths.log_file.resolve()
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and target == Path(handler.baseFilename):
            return logger
    handler = RotatingFileHandler(
        target,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.info("Local runtime logging initialized")
    return logger
