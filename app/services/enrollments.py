"""Shared helpers to serialize and evaluate enrollment records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Course, Enrollment, Notification, Student
from ..rules.engine import RuleSet


@dataclass(slots=True)
class EnrollmentEvaluation:
    """Container with serialization and rule evaluation metadata."""

    payload: dict[str, Any]
    rule_results: dict[str, Any]
    violations: list[str]


def serialize_enrollment(
    enrollment: Enrollment, student: Student, course: Course | None
) -> dict[str, Any]:
    """Return a normalized representation for API responses."""

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


def evaluate_enrollment(
    *,
    enrollment: Enrollment,
    student: Student,
    course: Course | None,
    ruleset: RuleSet,
) -> EnrollmentEvaluation:
    """Evaluate *enrollment* against configured rules and return metadata."""

    payload = serialize_enrollment(enrollment, student, course)
    rule_row = _build_rule_row(payload)
    rule_results = ruleset.evaluate({"row": rule_row})
    violations = [key for key, matched in rule_results.items() if matched]
    return EnrollmentEvaluation(payload=payload, rule_results=rule_results, violations=violations)


def summarize_notifications(
    session: Session, *, enrollment_ids: Iterable[int]
) -> dict[int, dict[str, int]]:
    """Return aggregated notification counts for given enrollments."""

    if not enrollment_ids:
        return {}

    rows = (
        session.query(Notification.enrollment_id, Notification.channel, func.count(Notification.id))
        .filter(Notification.enrollment_id.in_(list(enrollment_ids)))
        .group_by(Notification.enrollment_id, Notification.channel)
        .all()
    )

    summary: dict[int, dict[str, int]] = {}
    for enrollment_id, channel, count in rows:
        if enrollment_id is None:
            continue
        channel_counts = summary.setdefault(enrollment_id, {})
        channel_counts[str(channel)] = int(count)
    return summary


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


__all__ = [
    "EnrollmentEvaluation",
    "evaluate_enrollment",
    "serialize_enrollment",
    "summarize_notifications",
]
