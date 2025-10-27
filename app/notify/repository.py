"""Persistence helpers for notification audit entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.models import Job, JobEvent, Notification

from .dispatcher import NotificationAuditEntry


@dataclass(slots=True)
class SQLANotificationRepository:
    """Persist notification audit entries using a SQLAlchemy session factory."""

    session_factory: Callable[[], Session]

    def add(self, entry: NotificationAuditEntry) -> Notification:
        session = self.session_factory()
        try:
            job_record = None
            if entry.job_id:
                job_record = session.get(Job, entry.job_id)
                if job_record is None:
                    job_record = Job(
                        id=entry.job_id,
                        name=entry.job_name or entry.channel,
                        queue_name=entry.queue_name,
                        status=_map_job_status(entry.status),
                        payload=entry.payload,
                    )
                    session.add(job_record)
                else:
                    job_record.name = entry.job_name or job_record.name
                    job_record.queue_name = entry.queue_name or job_record.queue_name
                    job_record.status = _map_job_status(entry.status)
                    if entry.payload:
                        job_record.payload = entry.payload
                session.flush()

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
                job_id=entry.job_id,
            )
            if entry.status == "sent":
                record.sent_at = datetime.now(timezone.utc)
            session.add(record)
            if job_record is not None:
                event = JobEvent(
                    job_id=job_record.id,
                    event_type=f"notification.{entry.status}",
                    message=entry.error or entry.subject,
                    payload=entry.payload,
                )
                session.add(event)
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()


__all__ = ["SQLANotificationRepository"]


def _map_job_status(status: str) -> str:
    mapping = {
        "queued": "queued",
        "dry_run": "dry_run",
        "quiet_hours": "paused",
        "sent": "succeeded",
        "error": "failed",
    }
    return mapping.get(status, status)
