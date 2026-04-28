"""Structlog JSON logging configuration with per-request correlation IDs.

IMPORTANT: Bind correlation IDs at the START of each request handler (top of POST /analyze),
not inside concurrent module calls, to prevent cross-request context leakage.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
import structlog.contextvars


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog with JSON renderer and contextvars support.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            _level_to_int(level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _level_to_int(level: str) -> int:
    """Convert log level string to int.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Corresponding integer log level.
    """
    import logging

    return getattr(logging, level.upper(), logging.INFO)


def bind_correlation_id(job_id: str | None = None) -> str:
    """Bind a correlation ID to all subsequent logs in this context.

    Clears any previous context vars before binding the new ID to prevent
    correlation ID leakage between requests.

    Args:
        job_id: Optional correlation ID. If None, generates a random UUID.

    Returns:
        The correlation ID that was bound (either the provided job_id or a UUID).
    """
    cid = job_id or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def get_logger(**initial_context: Any) -> Any:
    """Get a structlog bound logger.

    Args:
        **initial_context: Initial context to bind to the logger.

    Returns:
        A structlog.BoundLogger instance.
    """
    return structlog.get_logger(**initial_context)
