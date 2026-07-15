"""Logging utilities for whatsapp-emovur.

Provides a small helper to get a configured logger and ensures structured
messages for request/response logging.
"""
import logging
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger for the given name.

    The root logger level is expected to be set by app.config.get_settings().
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
    return logger
