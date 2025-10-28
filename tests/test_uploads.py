from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pandas as pd
import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers


if "multipart" not in sys.modules:
    multipart_module = types.ModuleType("multipart")
    multipart_module.__version__ = "0.0.0-test"
    multipart_multipart = types.ModuleType("multipart.multipart")

    def _parse_options_header(value):
        if value is None:
            return "", {}
        if isinstance(value, bytes):
            value = value.decode()
        return value, {}

    multipart_multipart.parse_options_header = _parse_options_header  # type: ignore[attr-defined]
    multipart_multipart.parse_multipart_form = lambda *args, **kwargs: []  # type: ignore[attr-defined]

    sys.modules["multipart"] = multipart_module
    sys.modules["multipart.multipart"] = multipart_multipart

from app.api import uploads as uploads_module
from app.models import Base, Course, Enrollment, Student, UploadedFile
from app.modules.ingest.xlsx_importer import parse_xlsx


@pytest.fixture(scope="module")
def engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def valid_workbook(tmp_path) -> Path:
    data = {
        "Nombre": ["Ana", "Juan"],
        "Apellidos": ["García", "Rodríguez"],
        "Correo": ["ana@example.com", "juan@example.com"],
        "Primer acceso": ["21/10/2025", "No visitado"],
        "Último acceso": ["30/10/2025", "No visitado"],
        "Tiempo total": ["02h 15m 00s", "00h 00m 00s"],
    }
    dataframe = pd.DataFrame(data)
    workbook_path = tmp_path / "valid.xlsx"
    dataframe.to_excel(workbook_path, index=False, sheet_name="reporte")
    return workbook_path


def test_parse_xlsx_identifies_missing_columns(tmp_path):
    dataframe = pd.DataFrame({"Nombre": ["Grace"]})
    workbook_path = tmp_path / "invalid.xlsx"
    dataframe.to_excel(workbook_path, index=False, sheet_name="reporte")

    summary = parse_xlsx(workbook_path)

    assert "Correo" in summary.missing_columns
    assert any("Columnas faltantes" in error for error in summary.errors)


def test_upload_endpoint_creates_metadata_record(monkeypatch, tmp_path, db_session, valid_workbook):
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", tmp_path / "uploads")

    with valid_workbook.open("rb") as fh:
        contents = fh.read()

    spooled = SpooledTemporaryFile()
    spooled.write(contents)
    spooled.seek(0)

    headers = Headers({"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
    upload = UploadFile(file=spooled, filename="alumnos.xlsx", headers=headers)

    payload = asyncio.run(uploads_module.upload_file(file=upload, db=db_session))

    assert payload["file"]["original_name"] == "alumnos.xlsx"
    assert payload["file"]["size"] > 0
    assert payload["summary"]["missing_columns"] == []
    assert payload["summary"]["total_rows"] == 2
    assert payload["summary"]["preview"][0]["Nombre"] == "Ana"
    assert payload["summary"]["preview"][0]["Correo"] == "ana@example.com"
    assert payload["ingest"]["courses_created"] == 1
    assert payload["ingest"]["students_created"] == 2
    assert payload["ingest"]["enrollments_created"] == 2

    records = db_session.execute(select(UploadedFile)).scalars().all()

    assert len(records) == 1
    assert records[0].original_name == "alumnos.xlsx"
    assert records[0].stored_path.startswith("uploads/")

    course = db_session.execute(select(Course)).scalar_one()
    assert course.name == "Reporte Moodle alumnos"
    assert course.hours_required == 0

    students = db_session.execute(select(Student).order_by(Student.email)).scalars().all()
    assert {student.email for student in students} == {"ana@example.com", "juan@example.com"}
    assert students[0].full_name == "Ana García"
    assert students[0].course == course.name
    assert students[0].certificate_expires_at == course.deadline_date
    assert students[1].full_name == "Juan Rodríguez"
    assert students[1].certificate_expires_at == course.deadline_date

    enrollments = (
        db_session.execute(select(Enrollment).order_by(Enrollment.student_id))
        .scalars()
        .all()
    )
    assert len(enrollments) == 2
    progress_values = sorted(enrollment.progress_hours for enrollment in enrollments)
    assert progress_values == pytest.approx([0.0, 2.25])
    enrollment_map = {enrollment.student_id: enrollment for enrollment in enrollments}
    enrollment_by_email = {
        student.email: enrollment_map[student.id] for student in students
    }
    assert (
        enrollment_by_email["ana@example.com"].attributes["raw_total_time"]
        == "02h 15m 00s"
    )
    assert (
        enrollment_by_email["ana@example.com"].attributes["first_access_at"].startswith(
            "2025-10-21"
        )
    )
    assert (
        enrollment_by_email["juan@example.com"].attributes["raw_total_time"]
        == "00h 00m 00s"
    )
    assert "first_access_at" not in enrollment_by_email["juan@example.com"].attributes
