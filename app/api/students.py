"""Endpoints para consultar matrículas en riesgo de incumplimiento."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Course, Enrollment, Student
from app.rules.engine import RuleSet

router = APIRouter(prefix="/students", tags=["students"])

_RULESET_CACHE: RuleSet | None = None
_RULESET_PATH = Path(__file__).resolve().parents[1] / "rules" / "rulesets" / "enrollments.yaml"


def get_ruleset() -> RuleSet:
    """Carga perezosa del conjunto de reglas de vencimiento."""

    global _RULESET_CACHE
    if _RULESET_CACHE is None:
        _RULESET_CACHE = RuleSet.from_yaml(_RULESET_PATH)
    return _RULESET_CACHE


@router.get(
    "/non-compliance",
    summary="Listado de alumnos fuera de cumplimiento según reglas preventivas",
)
def list_non_compliant_students(
    *,
    course: str | None = Query(
        None, description="Filtra por nombre de curso (coincidencia parcial)"
    ),
    status: str | None = Query(
        None, description="Filtra por estado de la matrícula registrado en la plataforma"
    ),
    deadline_before: str | None = Query(
        None, description="Incluye matrículas con fecha límite anterior o igual a la indicada"
    ),
    deadline_after: str | None = Query(
        None, description="Incluye matrículas con fecha límite posterior o igual a la indicada"
    ),
    min_hours: float | None = Query(
        None, description="Mínimo de horas cursadas acumuladas"
    ),
    max_hours: float | None = Query(
        None, description="Máximo de horas cursadas acumuladas"
    ),
    rule: str | None = Query(
        None, description="Filtra por identificador de regla que debe cumplirse"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Devuelve matrículas marcadas como incumplidoras por las reglas declarativas."""

    course = _unwrap_str(course)
    status = _unwrap_str(status)
    rule = _unwrap_str(rule)
    deadline_before = _unwrap_str(deadline_before)
    deadline_after = _unwrap_str(deadline_after)
    min_hours = _unwrap_float(min_hours)
    max_hours = _unwrap_float(max_hours)
    limit = _unwrap_int(limit, 50)
    offset = _unwrap_int(offset, 0)

    deadline_before_date = _parse_date(deadline_before)
    deadline_after_date = _parse_date(deadline_after)

    query = (
        session.query(Enrollment, Student, Course)
        .join(Student, Enrollment.student_id == Student.id)
        .join(Course, Enrollment.course_id == Course.id, isouter=True)
    )

    if course:
        like = f"%{course}%"
        query = query.filter(Course.name.ilike(like))
    if status:
        query = query.filter(Enrollment.status == status)
    if deadline_before_date:
        query = query.filter(Course.deadline_date <= deadline_before_date)
    if deadline_after_date:
        query = query.filter(Course.deadline_date >= deadline_after_date)
    if min_hours is not None:
        query = query.filter(Enrollment.progress_hours >= min_hours)
    if max_hours is not None:
        query = query.filter(Enrollment.progress_hours <= max_hours)

    query = query.order_by(Course.deadline_date.asc())

    ruleset = get_ruleset()
    non_compliant_rows: list[dict[str, Any]] = []

    for enrollment, student, course_obj in query.all():
        payload = _serialize_row(enrollment, student, course_obj)
        rule_context = {"row": _build_rule_row(payload)}
        rule_results = ruleset.evaluate(rule_context)
        violations = [key for key, matched in rule_results.items() if matched]

        if rule and not rule_results.get(rule):
            continue
        if not violations:
            continue

        payload.update({
            "rule_results": rule_results,
            "violations": violations,
        })
        non_compliant_rows.append(payload)

    total = len(non_compliant_rows)
    paginated = non_compliant_rows[offset : offset + limit]

    return {"total": total, "items": paginated}


def _serialize_row(
    enrollment: Enrollment, student: Student, course: Course | None
) -> dict[str, Any]:
    return {
        "id": enrollment.id,
        "status": enrollment.status,
        "progress_hours": float(enrollment.progress_hours or 0.0),
        "last_notified_at": _to_iso(enrollment.last_notified_at),
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "email": student.email,
            "certificate_expires_at": _to_iso(student.certificate_expires_at),
        },
        "course": None
        if course is None
        else {
            "id": course.id,
            "name": course.name,
            "deadline_date": _to_iso(course.deadline_date),
            "hours_required": course.hours_required,
        },
        "deadline_date": _to_iso(course.deadline_date) if course else None,
        "hours_required": course.hours_required if course else None,
    }


def _build_rule_row(payload: dict[str, Any]) -> dict[str, Any]:
    course = payload.get("course") or {}
    student = payload.get("student") or {}
    return {
        "certificate_expires_at": student.get("certificate_expires_at"),
        "deadline_date": course.get("deadline_date"),
        "progress_hours": payload.get("progress_hours"),
        "hours_required": course.get("hours_required"),
        "status": payload.get("status"),
    }


def _to_iso(value: Any) -> str | None:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[call-arg]
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:  # pragma: no cover - validaciones defensivas
        return None


def _unwrap_str(value: Any) -> str | None:
    if isinstance(value, str) or value is None:
        return value
    return None


def _unwrap_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - fallback defensivo
        return default


def _unwrap_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - fallback defensivo
        return None


__all__ = ["router", "get_ruleset", "list_non_compliant_students"]
