import logging
import os
import json

__all__ = ["configure_logger"]


def configure_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return a logger configured with a standard formatter.

    The log level can be overridden via the ``LOG_LEVEL`` environment variable.
    """
    logger = logging.getLogger(name)
    log_level = os.getenv("LOG_LEVEL", level).upper()
    level_const = getattr(logging, log_level, logging.INFO)
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
    if os.getenv("LOG_JSON", "false").lower() == "true":
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

