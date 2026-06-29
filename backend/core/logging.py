"""Re-exports the project-wide logger so backend code doesn't import from `utils` directly."""

from __future__ import annotations

from utils.logger import get_logger

__all__ = ["get_logger"]
