"""Background queue client helpers backed by Redis/RQ."""
from __future__ import annotations

from redis import Redis
from rq import Queue

from .config import settings


redis_connection = Redis.from_url(settings.redis_url, decode_responses=False)
"""Shared Redis connection used by background workers."""

notification_queue = Queue(connection=redis_connection)
"""Default RQ queue for notification jobs."""


__all__ = ["redis_connection", "notification_queue"]
