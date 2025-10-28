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
        "Nombre completo": ["Ada Lovelace"],
        "Email": ["ada@example.com"],
        "Fecha caducidad": ["2024-12-01"],
        "Teléfono": ["123456789"],
        "Curso": ["Prevención de riesgos"],
        "Horas totales": [20],
        "Horas cursadas": [12.5],
        "Fecha caducidad curso": ["2024-12-31"],
    }
    dataframe = pd.DataFrame(data)
    workbook_path = tmp_path / "valid.xlsx"
    dataframe.to_excel(workbook_path, index=False)
    return workbook_path


def test_parse_xlsx_identifies_missing_columns(tmp_path):
    dataframe = pd.DataFrame({"Nombre completo": ["Grace Hopper"]})
    workbook_path = tmp_path / "invalid.xlsx"
    dataframe.to_excel(workbook_path, index=False)

    summary = parse_xlsx(workbook_path)

    assert "Email" in summary.missing_columns
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
    assert payload["summary"]["total_rows"] == 1
    assert payload["summary"]["preview"][0]["Nombre completo"] == "Ada Lovelace"
    assert payload["ingest"]["courses_created"] == 1
    assert payload["ingest"]["students_created"] == 1
    assert payload["ingest"]["enrollments_created"] == 1

    records = db_session.execute(select(UploadedFile)).scalars().all()

    assert len(records) == 1
    assert records[0].original_name == "alumnos.xlsx"
    assert records[0].stored_path.startswith("uploads/")

    course = db_session.execute(select(Course)).scalar_one()
    assert course.name == "Prevención de riesgos"
    assert course.hours_required == 20
    assert str(course.deadline_date) == "2024-12-31"

    student = db_session.execute(select(Student)).scalar_one()
    assert student.email == "ada@example.com"
    assert student.course == course.name
    assert str(student.certificate_expires_at) == "2024-12-01"

    enrollment = db_session.execute(select(Enrollment)).scalar_one()
    assert enrollment.course_id == course.id
    assert enrollment.student_id == student.id
    assert enrollment.progress_hours == pytest.approx(12.5)
    assert enrollment.attributes["certificate_expires_at"] == "2024-12-01"
    assert enrollment.attributes["course_deadline_date"] == "2024-12-31"
    assert enrollment.attributes["telefono"] == "123456789"
