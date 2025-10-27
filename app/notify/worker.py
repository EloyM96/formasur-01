"""RQ worker entry points to deliver notifications through adapters."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from app.config import settings
from app.db import SessionLocal
from app.logging import get_logger, job_context, reset_context
from app.notify.adapters import EmailSMTPAdapter
from app.notify.adapters.whatsapp_cli import WhatsAppCLIAdapter
from app.notify.dispatcher import NotificationDispatcher
from app.notify.repository import SQLANotificationRepository

try:  # pragma: no cover - optional dependency in tests
    from rq import get_current_job
except ModuleNotFoundError:  # pragma: no cover - fallback when RQ missing
    get_current_job = None


logger = get_logger(__name__)
reset_context()


def _create_dispatcher() -> NotificationDispatcher:
    adapters = {
        "email": EmailSMTPAdapter(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            from_email=settings.smtp_from_email or settings.smtp_username or None,
            use_tls=True,
        ),
        "whatsapp": WhatsAppCLIAdapter(),
    }
    repository = SQLANotificationRepository(session_factory=SessionLocal)
    return NotificationDispatcher(adapters=adapters, audit_repository=repository)


_dispatcher = _create_dispatcher()


def dispatch(
    *,
    playbook: str | None,
    action: Mapping[str, Any],
    row: Mapping[str, Any],
    rule_results: Mapping[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """Entry point executed by RQ workers."""

    resolved_job_id = job_id
    queue_name: str | None = None
    if get_current_job is not None:
        current = get_current_job()
        if current is not None:
            queue_name = getattr(current, "origin", None)
            resolved_job_id = resolved_job_id or current.id
    if resolved_job_id is None:
        resolved_job_id = f"rq-{uuid4().hex}"

    with job_context(
        job_id=resolved_job_id,
        job_name=_dispatcher.job_name,
        queue_name=queue_name,
        channel=str(action.get("channel", "default")).lower(),
    ):
        logger.info("worker.job.start", playbook=playbook)
        result = _dispatcher.deliver(
            playbook=playbook,
            action=action,
            row=row,
            rule_results=rule_results,
            dry_run=False,
            job_id=resolved_job_id,
            job_name=_dispatcher.job_name,
            queue_name=queue_name,
        )
        logger.info("worker.job.completed", status=result.get("status"))
        return result


__all__ = ["dispatch"]
