"""Centralized logging configuration shared across backend, etl, and frontend."""

from __future__ import annotations

import logging
import os
import sys

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with this project's shared format and level.

    Root configuration is applied once per process; later calls just look up
    the requested logger name.
    """
    _configure_root()
    return logging.getLogger(name)
