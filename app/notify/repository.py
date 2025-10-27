"""Persistence helpers for notification audit entries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.models import Notification

from .dispatcher import NotificationAuditEntry


@dataclass(slots=True)
class SQLANotificationRepository:
    """Persist notification audit entries using a SQLAlchemy session factory."""

    session_factory: Callable[[], Session]

    def add(self, entry: NotificationAuditEntry) -> Notification:
        session = self.session_factory()
        try:
            record = Notification(
                playbook=entry.playbook,
                channel=entry.channel,
                adapter=entry.adapter,
                recipient=entry.recipient,
                subject=entry.subject,
                status=entry.status,
                payload=entry.payload,
                response=entry.response,
                error=entry.error,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()


__all__ = ["SQLANotificationRepository"]
