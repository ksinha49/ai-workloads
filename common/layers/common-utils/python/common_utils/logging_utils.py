import logging
import os
import json

__all__ = ["configure_logger"]


def configure_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return a logger configured with a standard formatter.

    The log level can be overridden via the ``LOG_LEVEL`` environment variable.
    When ``LOG_JSON`` is ``true`` logs are formatted as JSON. Both options may
    also be supplied via Parameter Store under the same names.
    """
    try:  # late import to avoid circular dependency during package init
        from common_utils.get_ssm import get_config  # type: ignore
    except Exception:  # pragma: no cover - fallback if module not ready
        from typing import Optional

        def get_config(name: str) -> Optional[str]:  # type: ignore
            return None

    logger = logging.getLogger(name)

    log_level = os.getenv("LOG_LEVEL") or get_config("LOG_LEVEL") or level
    level_const = getattr(logging, str(log_level).upper(), logging.INFO)
    logger.setLevel(level_const)

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - trivial
            payload = {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            return json.dumps(payload)

    handler = logging.StreamHandler()
    json_flag = os.getenv("LOG_JSON") or get_config("LOG_JSON") or "false"
    if str(json_flag).lower() == "true":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            "%Y-%m-%dT%H:%M:%S%z",
        )
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

