"""Load Moodle PRL workbooks and persist courses, students and enrollments."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Course, Enrollment, Student
from . import xlsx_importer


DEFAULT_REQUIRED_HOURS = 6
DEFAULT_DEADLINE_GRACE_DAYS = 30


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
    workbook_label: str | None = None,
) -> LoaderResult:
    """Persist Moodle enrollments after validating the spreadsheet structure."""

    summary = xlsx_importer.parse_xlsx(
        file_path, mapping_path=mapping_path, preview_rows=5
    )

    stats = LoaderStats()
    if not summary.is_valid:
        return LoaderResult(summary=summary, stats=stats)

    mapping = xlsx_importer.load_mapping(mapping_path)
    column_map: dict[str, xlsx_importer.ColumnConfig] = mapping.get("columns", {})
    defaults: dict[str, Any] = mapping.get("defaults", {})
    sheet_name = mapping.get("sheet_name")

    dataframe = pd.read_excel(
        file_path,
        engine="openpyxl",
        sheet_name=sheet_name if sheet_name is not None else 0,
    )

    label_source = workbook_label or file_path.name
    context = build_normalization_context(
        file_path=file_path,
        workbook_label=Path(label_source).stem,
        dataframe=dataframe,
        column_map=column_map,
        defaults=defaults,
    )

    for normalized in iter_normalized_rows(
        dataframe, column_map=column_map, defaults=defaults, context=context
    ):

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
        hours_required = normalized.get("progress_hours") or 0
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

    first_access = normalized.get("first_access_at")
    if isinstance(first_access, datetime):
        attributes["first_access_at"] = first_access.isoformat()
    elif isinstance(first_access, date):
        attributes["first_access_at"] = datetime.combine(first_access, datetime.min.time()).isoformat()

    last_access = normalized.get("last_access_at")
    if isinstance(last_access, datetime):
        attributes["last_access_at"] = last_access.isoformat()
    elif isinstance(last_access, date):
        attributes["last_access_at"] = datetime.combine(last_access, datetime.min.time()).isoformat()

    raw_total_time = normalized.get("raw_total_time")
    if raw_total_time:
        attributes["raw_total_time"] = str(raw_total_time)

    return attributes


def build_normalization_context(
    *,
    file_path: Path,
    workbook_label: str,
    dataframe: pd.DataFrame,
    column_map: dict[str, xlsx_importer.ColumnConfig],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Derive contextual defaults shared by normalization and workflows."""

    context = {
        "workbook_stem": file_path.stem,
        "workbook_label": workbook_label,
    }

    dynamic_defaults = _derive_dynamic_defaults(
        dataframe=dataframe, column_map=column_map, defaults=defaults
    )
    context.update(dynamic_defaults)
    return context


def iter_normalized_rows(
    dataframe: pd.DataFrame,
    *,
    column_map: dict[str, xlsx_importer.ColumnConfig],
    defaults: dict[str, Any],
    context: dict[str, Any],
) -> Iterable[dict[str, Any]]:
    """Yield normalized rows ready for persistence or rule evaluation."""

    for raw_row in dataframe.to_dict(orient="records"):
        yield _normalize_row(raw_row, column_map, defaults, context)


def _normalize_row(
    raw_row: dict[str, Any],
    column_map: dict[str, xlsx_importer.ColumnConfig],
    defaults: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    def get_value(key: str) -> Any:
        config = column_map.get(key)
        if config is None:
            return None
        for column in config.sources:
            value = raw_row.get(column)
            if value is None:
                continue
            if isinstance(value, float) and pd.isna(value):
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    continue
                return stripped
            if pd.isna(value):  # type: ignore[arg-type]
                continue
            return value
        return None

    def get_default(key: str) -> Any:
        if key not in defaults:
            return None
        value = defaults[key]
        if isinstance(value, str):
            try:
                return value.format(**context)
            except (KeyError, ValueError):  # pragma: no cover - defensive
                return value
        return value

    normalized: dict[str, Any] = {}

    first_name = get_value("first_name")
    last_name = get_value("last_name")
    full_name_parts = [part for part in [first_name, last_name] if part]
    normalized["full_name"] = " ".join(full_name_parts) or get_value("full_name")
    if not normalized["full_name"]:
        normalized["full_name"] = get_default("full_name") or get_value("email")

    normalized["email"] = get_value("email")

    telefono = get_value("telefono")
    if telefono is None:
        telefono = get_default("telefono")
    normalized["telefono"] = str(telefono) if telefono is not None else None

    course_name = get_value("course_name")
    if course_name is None:
        course_name = get_default("course_name")
    normalized["course_name"] = course_name

    hours_required = get_value("course_hours_required")
    if hours_required is None:
        hours_required = get_default("course_hours_required")
    hours_value = _to_float(hours_required)
    normalized["course_hours_required"] = (
        int(math.ceil(hours_value)) if hours_value is not None else None
    )

    deadline = get_value("course_deadline_date")
    if deadline is None:
        deadline = get_default("course_deadline_date")
    normalized["course_deadline_date"] = _to_date(deadline)

    certificate = get_value("certificate_expires_at")
    if certificate is None:
        certificate = get_default("certificate_expires_at")
    normalized["certificate_expires_at"] = _to_date(certificate)

    progress = get_value("progress_hours")
    progress_float = _to_float(progress)
    raw_total_time = get_value("total_time")
    duration_hours = _to_duration_hours(raw_total_time)
    normalized["progress_hours"] = (
        progress_float
        if progress_float is not None
        else (duration_hours if duration_hours is not None else 0.0)
    )

    normalized["raw_total_time"] = raw_total_time
    normalized["first_access_at"] = _to_datetime(get_value("first_access"))
    normalized["last_access_at"] = _to_datetime(get_value("last_access"))

    for key in column_map.keys():
        if key in normalized:
            continue
        value = get_value(key)
        if value is None:
            value = get_default(key)
        normalized[key] = value

    return normalized


def _derive_dynamic_defaults(
    *,
    dataframe: pd.DataFrame,
    column_map: dict[str, xlsx_importer.ColumnConfig],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Compute hours and deadlines when the workbook omits them."""

    hours_required = _extract_hours_required(dataframe, column_map)
    if hours_required is None:
        hours_required = _fallback_hours(defaults)

    deadline_date = _extract_deadline_date(dataframe, column_map)
    if deadline_date is None:
        deadline_date = date.today() + timedelta(days=DEFAULT_DEADLINE_GRACE_DAYS)

    certificate_date = _extract_certificate_date(dataframe, column_map)
    if certificate_date is None:
        certificate_date = deadline_date

    return {
        "default_course_hours_required": hours_required,
        "default_course_deadline_date": deadline_date,
        "default_certificate_expires_at": certificate_date,
    }


def _extract_hours_required(
    dataframe: pd.DataFrame, column_map: dict[str, xlsx_importer.ColumnConfig]
) -> int | None:
    source = column_map.get("course_hours_required")
    if source:
        for column in source.sources:
            if column in dataframe.columns:
                values = dataframe[column].dropna().tolist()
                parsed = [_to_float(value) for value in values]
                numbers = [value for value in parsed if value is not None]
                if numbers:
                    return int(math.ceil(max(numbers)))

    total_time_config = column_map.get("total_time")
    durations: list[float] = []
    if total_time_config:
        for column in total_time_config.sources:
            if column not in dataframe.columns:
                continue
            durations.extend(
                value
                for value in (
                    _to_duration_hours(raw) for raw in dataframe[column].tolist()
                )
                if value is not None
            )
    if durations:
        max_duration = max(durations)
        if max_duration > 0:
            return int(math.ceil(max_duration))
    return None


def _fallback_hours(defaults: dict[str, Any]) -> int:
    raw_default = defaults.get("course_hours_required")
    if raw_default is not None:
        value = _to_float(raw_default)
        if value is not None and value > 0:
            return int(math.ceil(value))
    return DEFAULT_REQUIRED_HOURS


def _extract_deadline_date(
    dataframe: pd.DataFrame, column_map: dict[str, xlsx_importer.ColumnConfig]
) -> date | None:
    source = column_map.get("course_deadline_date")
    if source:
        for column in source.sources:
            if column in dataframe.columns:
                dates = [
                    _to_date(value)
                    for value in dataframe[column].dropna().tolist()
                    if value is not None
                ]
                filtered = [value for value in dates if value is not None]
                if filtered:
                    return max(filtered)

    access_dates: list[date] = []
    for key in ("last_access", "first_access"):
        config = column_map.get(key)
        if not config:
            continue
        for column in config.sources:
            if column not in dataframe.columns:
                continue
            for value in dataframe[column].tolist():
                access_date = _to_date(value)
                if access_date is not None:
                    access_dates.append(access_date)
    if access_dates:
        return max(access_dates) + timedelta(days=DEFAULT_DEADLINE_GRACE_DAYS)
    return None


def _extract_certificate_date(
    dataframe: pd.DataFrame, column_map: dict[str, xlsx_importer.ColumnConfig]
) -> date | None:
    source = column_map.get("certificate_expires_at")
    if source:
        for column in source.sources:
            if column in dataframe.columns:
                dates = [
                    _to_date(value)
                    for value in dataframe[column].dropna().tolist()
                    if value is not None
                ]
                filtered = [value for value in dates if value is not None]
                if filtered:
                    return max(filtered)
    return None


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "no visitado":
            return None
        dayfirst = "/" in cleaned
        parsed = pd.to_datetime(cleaned, errors="coerce", dayfirst=dayfirst)
        if pd.isna(parsed):
            return None
        return parsed.date()
    return None


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "no visitado":
            return None
        parsed = pd.to_datetime(cleaned, errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    return None


def _to_float(value: Any) -> float | None:
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


def _to_duration_hours(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):  # type: ignore[arg-type]
            return None
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "no visitado":
            return 0.0
        total_seconds = 0
        for amount, unit in re.findall(r"(\d+)\s*([hms])", cleaned.lower()):
            quantity = int(amount)
            if unit == "h":
                total_seconds += quantity * 3600
            elif unit == "m":
                total_seconds += quantity * 60
            elif unit == "s":
                total_seconds += quantity
        if total_seconds == 0:
            numeric = _to_float(cleaned)
            if numeric is not None:
                return numeric
            return None
        return total_seconds / 3600
    return None


__all__ = [
    "LoaderResult",
    "LoaderStats",
    "build_normalization_context",
    "ingest_workbook",
    "iter_normalized_rows",
]
