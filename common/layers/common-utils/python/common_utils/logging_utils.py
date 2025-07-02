import logging
import os

__all__ = ["configure_logger"]


def configure_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return a logger configured with a standard formatter.

    The log level can be overridden via the ``LOG_LEVEL`` environment variable.
    """
    logger = logging.getLogger(name)
    log_level = os.getenv("LOG_LEVEL", level).upper()
    level_const = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level_const)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            "%Y-%m-%dT%H:%M:%S%z",
        )
    )
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

