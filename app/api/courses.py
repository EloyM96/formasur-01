"""Course-centric endpoints exposing enrollment status and notifications."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Course, CourseModel, Enrollment, Notification, Student
from app.rules.engine import RuleSet
from app.services import enrollments as enrollment_service

router = APIRouter(prefix="/courses", tags=["courses"])

_RULESET_CACHE: RuleSet | None = None


def get_ruleset() -> RuleSet:
    """Return cached enrollment rule set for course summaries."""

    global _RULESET_CACHE
    if _RULESET_CACHE is None:
        _RULESET_CACHE = RuleSet.from_yaml(
            Path(__file__).resolve().parents[1]
            / "rules"
            / "rulesets"
            / "enrollments.yaml"
        )
    return _RULESET_CACHE


class CourseUpdatePayload(BaseModel):
    """Payload used to update course metadata manually."""

    deadline_date: date | None = Field(
        default=None,
        description="Fecha límite para completar el curso",
    )
    hours_required: int | None = Field(
        default=None,
        ge=0,
        description="Horas totales exigidas por el curso",
    )


@router.get("", summary="Resumen de cursos con métricas de seguimiento")
def list_courses(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return course summaries including compliance and notification metrics."""

    ruleset = get_ruleset()
    courses = session.query(Course).order_by(Course.deadline_date.asc()).all()

    enrollment_rows = (
        session.query(Enrollment, Student, Course)
        .join(Student, Enrollment.student_id == Student.id)
        .join(Course, Enrollment.course_id == Course.id)
        .all()
    )

    enrollments_by_course: dict[int, list[tuple[Enrollment, Student, Course]]] = {}
    for enrollment, student, course in enrollment_rows:
        if course.id is None:
            continue
        enrollments_by_course.setdefault(course.id, []).append((enrollment, student, course))

    notification_counts_by_course = _notifications_by_course(session)

    items: list[dict[str, Any]] = []
    for course in courses:
        course_payload = CourseModel.model_validate(course).model_dump()
        enrolled = enrollments_by_course.get(course.id or 0, [])
        evaluations = [
            enrollment_service.evaluate_enrollment(
                enrollment=enrollment,
                student=student,
                course=course,
                ruleset=ruleset,
            )
            for enrollment, student, _ in enrolled
        ]

        non_compliant = sum(1 for ev in evaluations if ev.violations)
        zero_hours = sum(
            1
            for ev in evaluations
            if (ev.payload.get("progress_hours") or 0) <= 0
        )

        items.append(
            {
                "course": course_payload,
                "metrics": {
                    "total_enrollments": len(enrolled),
                    "non_compliant_enrollments": non_compliant,
                    "zero_hours_enrollments": zero_hours,
                },
                "notifications": {
                    "total": sum(notification_counts_by_course.get(course.id or 0, {}).values()),
                    "by_channel": notification_counts_by_course.get(course.id or 0, {}),
                },
            }
        )

    return {"total": len(items), "items": items}


@router.get("/{course_id}", summary="Detalle del curso con matrículas evaluadas")
def course_detail(
    *,
    course_id: int = Path(..., ge=1, description="Identificador del curso"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return course detail with per-enrollment evaluation and notification counts."""

    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    ruleset = get_ruleset()

    rows = (
        session.query(Enrollment, Student)
        .join(Student, Enrollment.student_id == Student.id)
        .filter(Enrollment.course_id == course_id)
        .all()
    )

    enrollment_ids = [enrollment.id for enrollment, _ in rows if enrollment.id is not None]
    notifications = enrollment_service.summarize_notifications(
        session, enrollment_ids=enrollment_ids
    )

    students_payload: list[dict[str, Any]] = []
    for enrollment, student in rows:
        evaluation = enrollment_service.evaluate_enrollment(
            enrollment=enrollment,
            student=student,
            course=course,
            ruleset=ruleset,
        )

        enrollment_id = enrollment.id or 0
        channel_counts = notifications.get(enrollment_id, {})
        students_payload.append(
            {
                "enrollment": evaluation.payload,
                "rule_results": evaluation.rule_results,
                "violations": evaluation.violations,
                "has_no_activity": (evaluation.payload.get("progress_hours") or 0) <= 0,
                "notifications": {
                    "total": sum(channel_counts.values()),
                    "by_channel": channel_counts,
                },
            }
        )

    return {
        "course": CourseModel.model_validate(course).model_dump(),
        "students": students_payload,
    }


@router.patch("/{course_id}", summary="Actualiza manualmente los metadatos del curso")
def update_course(
    *,
    course_id: int = Path(..., ge=1, description="Identificador del curso"),
    payload: CourseUpdatePayload,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Allow operators to override course metadata not present in the XLSX."""

    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    updated = False
    if payload.deadline_date is not None and course.deadline_date != payload.deadline_date:
        course.deadline_date = payload.deadline_date
        updated = True
    if payload.hours_required is not None and course.hours_required != payload.hours_required:
        course.hours_required = payload.hours_required
        updated = True

    if updated:
        session.add(course)
        session.commit()
        session.refresh(course)

    return CourseModel.model_validate(course).model_dump()


def _notifications_by_course(session: Session) -> dict[int, dict[str, int]]:
    """Aggregate notification counts per course for summaries."""

    rows = (
        session.query(Course.id, Notification.channel, func.count(Notification.id))
        .join(Enrollment, Enrollment.course_id == Course.id)
        .join(Notification, Notification.enrollment_id == Enrollment.id, isouter=True)
        .group_by(Course.id, Notification.channel)
        .all()
    )

    summary: dict[int, dict[str, int]] = {}
    for course_id, channel, count in rows:
        if course_id is None or channel is None:
            continue
        channel_counts = summary.setdefault(int(course_id), {})
        channel_counts[str(channel)] = int(count)
    return summary


__all__ = [
    "router",
    "list_courses",
    "course_detail",
    "update_course",
    "get_ruleset",
    "CourseUpdatePayload",
]
