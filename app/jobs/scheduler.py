"""Simple scheduler wrapper honouring quiet hours for notifications."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable

try:  # pragma: no cover - import when dependency available
    from apscheduler.schedulers.background import BackgroundScheduler
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback
    class BackgroundScheduler:  # type: ignore[override]
        def __init__(self):
            self.running = False

        def add_job(self, *_args, **_kwargs):  # noqa: D401 - mimic APScheduler API
            """Store job metadata (no-op in the fallback implementation)."""

        def start(self, paused: bool = True):
            self.running = not paused

        def shutdown(self, wait: bool = False):
            self.running = False


@dataclass(slots=True)
class QuietHours:
    """Represents the daily time window where notifications must be paused."""

    start: time
    end: time

    def allows(self, now: datetime) -> bool:
        """Return True when the provided datetime is outside the quiet window."""

        current = now.time()
        if self.start < self.end:
            return not (self.start <= current < self.end)
        # Quiet hours span across midnight
        return self.end <= current < self.start


class Scheduler:
    """Thin wrapper around APScheduler to illustrate background job setup."""

    def __init__(self, quiet_hours: QuietHours | None = None):
        self.quiet_hours = quiet_hours
        self._scheduler = BackgroundScheduler()

    def schedule_interval(
        self,
        job_id: str,
        func: Callable[..., None],
        minutes: int,
    ) -> None:
        """Schedule a callable to run every *minutes* minutes respecting quiet hours."""

        def wrapper():
            if self.quiet_hours and not self.quiet_hours.allows(datetime.utcnow()):
                return
            func()

        self._scheduler.add_job(
            wrapper,
            "interval",
            id=job_id,
            minutes=minutes,
            replace_existing=True,
        )

    def start(self) -> None:
        """Start the underlying scheduler."""

        if not self._scheduler.running:
            self._scheduler.start(paused=True)

    def shutdown(self) -> None:
        """Stop the underlying scheduler."""

        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)


__all__ = ["QuietHours", "Scheduler"]
