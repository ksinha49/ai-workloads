from __future__ import annotations

"""Helpers for consistent error logging and responses."""

from typing import Any, Dict
import logging

from .lambda_response import lambda_response

__all__ = ["error_response", "log_exception"]


def log_exception(message: str, exc: Exception, logger: logging.Logger) -> None:
    """Log ``exc`` with ``message`` using ``logger``."""

    logger.error("%s: %s", message, exc)


def error_response(
    logger: logging.Logger, status: int, message: str, exc: Exception | None = None
) -> Dict[str, Any]:
    """Return ``lambda_response`` with error details after logging ``message``."""

    if exc is not None:
        logger.error("%s: %s", message, exc)
    else:
        logger.error("%s", message)
    return lambda_response(status, {"error": message})
