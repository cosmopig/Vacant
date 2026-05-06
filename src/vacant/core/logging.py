"""Structured logging setup for Vacant.

Single entry point: :func:`configure_logging`. Call it once at process start
(`vacant serve`, `vacant demo`, dashboard, integration test fixtures).

Default behavior:
- Pretty console renderer when stdout is a TTY.
- JSON renderer otherwise (CI, log aggregation, container stdout).
- Level controlled by env `VACANT_LOG_LEVEL` (default `INFO`); accepts
  `DEBUG / INFO / WARNING / ERROR`.
- All log records carry `vacant_id`, `module`, `event`, and `timestamp`
  fields. Use `bind(...)` on the returned logger to attach per-vacant or
  per-call context.

This module imports `structlog` lazily so importing `vacant.core` doesn't
force users to install it (it's listed in runtime deps but kept out of the
import path of pure-types modules).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

__all__ = [
    "configure_logging",
    "get_logger",
]


def _level_from_env() -> int:
    raw = os.environ.get("VACANT_LOG_LEVEL", "INFO").upper()
    return getattr(logging, raw, logging.INFO)


def configure_logging(
    *,
    level: int | None = None,
    json_only: bool = False,
    capture_warnings: bool = True,
) -> None:
    """Configure structlog + stdlib logging once. Idempotent.

    Args:
        level: override log level (default: env `VACANT_LOG_LEVEL`).
        json_only: force JSON output even on a TTY (useful for tests
            asserting machine-readable structure).
        capture_warnings: route `warnings.warn` into the log stream.
    """
    import structlog

    resolved_level = level if level is not None else _level_from_env()
    is_tty = sys.stdout.isatty() and not json_only

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: structlog.types.Processor
    if is_tty:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging → structlog so libraries (uvicorn, sqlalchemy,
    # alembic, anthropic SDK) emit through the same renderer.
    logging.basicConfig(
        level=resolved_level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    if capture_warnings:
        logging.captureWarnings(True)


def get_logger(name: str | None = None, **initial_context: Any) -> Any:
    """Return a bound structlog logger.

    Equivalent to ``structlog.get_logger(name).bind(**initial_context)``.
    Doesn't trigger configuration — call :func:`configure_logging` first
    (or rely on structlog's defaults if you don't).
    """
    import structlog

    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger
