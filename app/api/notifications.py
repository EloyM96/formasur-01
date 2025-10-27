"""Endpoints to explore notification audit trails."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Notification, NotificationModel

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", summary="Listado paginado de notificaciones")
def list_notifications(
    *,
    status: str | None = Query(None, description="Filtra por estado de entrega"),
    channel: str | None = Query(None, description="Filtra por canal de comunicación"),
    playbook: str | None = Query(None, description="Filtra por playbook"),
    adapter: str | None = Query(None, description="Filtra por adaptador técnico"),
    recipient: str | None = Query(None, description="Filtra por destinatario exacto"),
    job_id: str | None = Query(None, description="Filtra por identificador de job"),
    search: str | None = Query(
        None, description="Criterio parcial sobre asunto o destinatario"
    ),
    date_from: str | None = Query(None, description="Fecha/hora mínima en ISO-8601"),
    date_to: str | None = Query(None, description="Fecha/hora máxima en ISO-8601"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return a page of notification audits using the provided filters."""

    status = _unwrap_query(status)
    channel = _unwrap_query(channel)
    playbook = _unwrap_query(playbook)
    adapter = _unwrap_query(adapter)
    recipient = _unwrap_query(recipient)
    job_id = _unwrap_query(job_id)
    search = _unwrap_query(search)
    date_from = _unwrap_query(date_from)
    date_to = _unwrap_query(date_to)
    limit = _unwrap_int(limit, 50)
    offset = _unwrap_int(offset, 0)

    query = session.query(Notification)

    if status:
        query = query.filter(Notification.status == status)
    if channel:
        query = query.filter(Notification.channel == channel)
    if playbook:
        query = query.filter(Notification.playbook == playbook)
    if adapter:
        query = query.filter(Notification.adapter == adapter)
    if recipient:
        query = query.filter(Notification.recipient == recipient)
    if job_id:
        query = query.filter(Notification.job_id == job_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Notification.recipient.ilike(like), Notification.subject.ilike(like))
        )

    if date_from:
        parsed = _parse_datetime(date_from)
        if parsed:
            query = query.filter(Notification.created_at >= parsed)
    if date_to:
        parsed = _parse_datetime(date_to)
        if parsed:
            query = query.filter(Notification.created_at <= parsed)

    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    )

    payload = [NotificationModel.model_validate(item).model_dump() for item in items]
    return {"total": total, "items": payload}


@router.get("/metadata", summary="Valores disponibles para los filtros")
def metadata(session: Session = Depends(get_session)) -> dict[str, list[str]]:
    """Return distinct values used by the audit listings for UI helpers."""

    channels = [
        row[0] for row in session.query(Notification.channel).distinct().all() if row[0]
    ]
    statuses = [
        row[0] for row in session.query(Notification.status).distinct().all() if row[0]
    ]
    adapters = [
        row[0] for row in session.query(Notification.adapter).distinct().all() if row[0]
    ]
    playbooks = [
        row[0]
        for row in session.query(Notification.playbook).distinct().all()
        if row[0]
    ]
    job_ids = [
        row[0] for row in session.query(Notification.job_id).distinct().all() if row[0]
    ]

    return {
        "channels": sorted(channels),
        "statuses": sorted(statuses),
        "adapters": sorted(adapters),
        "playbooks": sorted(playbooks),
        "jobs": sorted(job_ids),
    }


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:  # pragma: no cover - defensive against malformed input
        return None


def _unwrap_query(value: Any) -> str | None:
    if isinstance(value, str) or value is None:
        return value
    return None


def _unwrap_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        return default


__all__ = ["router"]
