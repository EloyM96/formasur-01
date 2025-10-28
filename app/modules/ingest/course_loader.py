"""Load Moodle PRL workbooks and persist courses, students and enrollments."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Course, Enrollment, Student
from . import xlsx_importer


@dataclass(slots=True)
class LoaderStats:
    """Counters describing entities created or updated during ingestion."""

    courses_created: int = 0
    courses_updated: int = 0
    students_created: int = 0
    students_updated: int = 0
    enrollments_created: int = 0
    enrollments_updated: int = 0


@dataclass(slots=True)
class LoaderResult:
    """Aggregate information produced while loading a Moodle workbook."""

    summary: xlsx_importer.ImportSummary
    stats: LoaderStats


def ingest_workbook(
    file_path: Path,
    db: Session,
    *,
    mapping_path: Path | None = None,
) -> LoaderResult:
    """Persist Moodle enrollments after validating the spreadsheet structure."""

    summary = xlsx_importer.parse_xlsx(
        file_path, mapping_path=mapping_path, preview_rows=5
    )

    stats = LoaderStats()
    if not summary.is_valid:
        return LoaderResult(summary=summary, stats=stats)

    mapping = xlsx_importer.load_mapping(mapping_path).get("columns", {})
    dataframe = pd.read_excel(file_path, engine="openpyxl")

    for raw_row in dataframe.to_dict(orient="records"):
        normalized = _normalize_row(raw_row, mapping)

        email = normalized.get("email")
        if not email:
            continue

        course = _get_or_create_course(db, normalized, stats)
        student = _get_or_create_student(db, normalized, course, stats)
        _get_or_create_enrollment(db, normalized, student, course, stats)

    db.commit()

    return LoaderResult(summary=summary, stats=stats)


def _get_or_create_course(
    db: Session, normalized: dict[str, Any], stats: LoaderStats
) -> Course:
    name = normalized.get("course_name") or "Curso sin nombre"
    hours_required = normalized.get("course_hours_required")
    if hours_required is None:
        hours_required = int(normalized.get("progress_hours") or 0)
    deadline_date = normalized.get("course_deadline_date")
    certificate_date = normalized.get("certificate_expires_at")
    if deadline_date is None:
        deadline_date = certificate_date or date.today()

    course = db.execute(select(Course).where(Course.name == name)).scalar_one_or_none()
    if course is None:
        course = Course(
            name=name,
            hours_required=int(hours_required),
            deadline_date=deadline_date,
            source="xlsx",
        )
        db.add(course)
        db.flush()
        stats.courses_created += 1
        return course

    updated = False
    if course.hours_required != int(hours_required):
        course.hours_required = int(hours_required)
        updated = True
    if course.deadline_date != deadline_date:
        course.deadline_date = deadline_date
        updated = True
    if updated:
        stats.courses_updated += 1

    return course


def _get_or_create_student(
    db: Session,
    normalized: dict[str, Any],
    course: Course,
    stats: LoaderStats,
) -> Student:
    email = normalized["email"]
    full_name = normalized.get("full_name") or email
    certificate_date = (
        normalized.get("certificate_expires_at")
        or normalized.get("course_deadline_date")
        or date.today()
    )

    student = db.execute(select(Student).where(Student.email == email)).scalar_one_or_none()
    if student is None:
        student = Student(
            full_name=full_name,
            email=email,
            course=course.name,
            certificate_expires_at=certificate_date,
        )
        db.add(student)
        db.flush()
        stats.students_created += 1
        return student

    updated = False
    if student.full_name != full_name:
        student.full_name = full_name
        updated = True
    if student.course != course.name:
        student.course = course.name
        updated = True
    if student.certificate_expires_at != certificate_date:
        student.certificate_expires_at = certificate_date
        updated = True
    if updated:
        stats.students_updated += 1

    return student


def _get_or_create_enrollment(
    db: Session,
    normalized: dict[str, Any],
    student: Student,
    course: Course,
    stats: LoaderStats,
) -> Enrollment:
    progress_hours = normalized.get("progress_hours") or 0.0
    attributes = _build_enrollment_attributes(normalized)

    enrollment = db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student.id, Enrollment.course_id == course.id
        )
    ).scalar_one_or_none()

    if enrollment is None:
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
            progress_hours=progress_hours,
            attributes=attributes,
        )
        db.add(enrollment)
        stats.enrollments_created += 1
        return enrollment

    updated = False
    if abs(enrollment.progress_hours - progress_hours) > 1e-6:
        enrollment.progress_hours = progress_hours
        updated = True
    if (enrollment.attributes or {}) != attributes:
        enrollment.attributes = attributes
        updated = True
    if updated:
        stats.enrollments_updated += 1

    return enrollment


def _build_enrollment_attributes(normalized: dict[str, Any]) -> dict[str, Any]:
    attributes: dict[str, Any] = {}

    certificate = normalized.get("certificate_expires_at")
    if isinstance(certificate, date):
        attributes["certificate_expires_at"] = certificate.isoformat()

    deadline = normalized.get("course_deadline_date")
    if isinstance(deadline, date):
        attributes["course_deadline_date"] = deadline.isoformat()

    telefono = normalized.get("telefono")
    if telefono:
        attributes["telefono"] = str(telefono)

    return attributes


def _normalize_row(
    raw_row: dict[str, Any], column_map: dict[str, str]
) -> dict[str, Any]:
    def get_value(key: str) -> Any:
        column = column_map.get(key)
        if not column:
            return None
        value = raw_row.get(column)
        if isinstance(value, float) and pd.isna(value):
            return None
        if pd.isna(value):  # type: ignore[arg-type]
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    def to_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.date()
        return None

    def to_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if pd.isna(value):  # type: ignore[arg-type]
                return None
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    normalized: dict[str, Any] = {}

    normalized["full_name"] = get_value("full_name")
    normalized["email"] = get_value("email")
    telefono = get_value("telefono")
    normalized["telefono"] = str(telefono) if telefono is not None else None
    normalized["course_name"] = get_value("course_name")
    normalized["course_hours_required"] = None

    hours_required = get_value("course_hours_required")
    if hours_required is not None:
        hours_value = to_float(hours_required)
        if hours_value is not None:
            normalized["course_hours_required"] = int(round(hours_value))

    normalized["course_deadline_date"] = to_date(get_value("course_deadline_date"))
    normalized["certificate_expires_at"] = to_date(
        get_value("certificate_expires_at")
    )
    normalized["progress_hours"] = to_float(get_value("progress_hours")) or 0.0

    return normalized


__all__ = ["LoaderResult", "LoaderStats", "ingest_workbook"]
