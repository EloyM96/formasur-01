"""Centralised logging configuration using structlog with graceful fallbacks."""

from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from typing import Any, Iterator

try:  # pragma: no cover - prefer structlog when available
    import structlog
    from structlog import stdlib
    from structlog.contextvars import (
        bind_contextvars,
        clear_contextvars,
        unbind_contextvars,
    )
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for offline tests
    structlog = None  # type: ignore[assignment]
    stdlib = None  # type: ignore[assignment]

    def bind_contextvars(**_kwargs: Any) -> None:  # type: ignore[override]
        return None

    def clear_contextvars() -> None:  # type: ignore[override]
        return None

    def unbind_contextvars(*_args: str) -> None:  # type: ignore[override]
        return None


_LOGGING_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Initialise structlog with a JSON formatter and contextvars support."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    if structlog is None:
        _LOGGING_CONFIGURED = True
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.filter_by_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=stdlib.BoundLogger,
        logger_factory=stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _LOGGING_CONFIGURED = True


def get_logger(name: str | None = None):
    """Return a structlog logger ensuring the configuration is ready."""

    configure_logging()
    if structlog is None:
        return _FallbackLogger(name)
    return structlog.get_logger(name)


@contextmanager
def job_context(**values: Any) -> Iterator[None]:
    """Bind and automatically clean job-related context variables."""

    if not values:
        yield
        return
    configure_logging()
    if structlog is None:
        try:
            yield
        finally:
            pass
    else:
        bind_contextvars(**values)
        try:
            yield
        finally:
            unbind_contextvars(*values.keys())


def reset_context() -> None:
    """Remove all bound context variables, useful for worker bootstrap."""

    configure_logging()
    if structlog is not None:
        clear_contextvars()


__all__ = ["configure_logging", "get_logger", "job_context", "reset_context"]


class _FallbackLogger:
    """Minimal logger that emulates structlog's keyword-based API."""

    def __init__(self, name: str | None) -> None:
        self._logger = logging.getLogger(name or "app")

    def debug(self, event: str, **kwargs: Any) -> None:
        self._logger.debug(self._format(event, kwargs))

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info(self._format(event, kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning(self._format(event, kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error(self._format(event, kwargs))

    def exception(self, event: str, **kwargs: Any) -> None:
        self._logger.exception(self._format(event, kwargs))

    def _format(self, event: str, payload: dict[str, Any]) -> str:
        if not payload:
            return event
        try:
            serialized = json.dumps(
                payload, default=str, ensure_ascii=False, sort_keys=True
            )
        except TypeError:  # pragma: no cover - defensive fallback
            serialized = str(payload)
        return f"{event} | {serialized}"
