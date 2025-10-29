from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.integrations.prevengos import (
    PrevengosAPIClient,
    PrevengosCSVAdapter,
    PrevengosDBAdapter,
    PrevengosIntegrationError,
    PrevengosSyncService,
    PrevengosTrainingRecord,
)
from app.integrations.prevengos.models import ISO_FORMAT


@pytest.fixture()
def sample_record() -> PrevengosTrainingRecord:
    return PrevengosTrainingRecord(
        employee_nif="12345678A",
        contract_code="C-001",
        course_code="PRL-BASICO",
        status="completed",
        hours_completed=6.0,
        last_update=datetime(2024, 4, 1, 10, 0, tzinfo=timezone.utc),
    )


def test_csv_adapter_roundtrip(tmp_path: Path, sample_record: PrevengosTrainingRecord) -> None:
    csv_path = tmp_path / "prevengos" / "training.csv"
    adapter = PrevengosCSVAdapter(csv_path)

    adapter.write_records([sample_record])
    roundtrip = adapter.read_records()

    assert roundtrip == [sample_record]
    assert csv_path.read_text(encoding="utf-8-sig").splitlines()[0].startswith(
        "employee_nif"
    )


def test_api_client_fetch_and_push(sample_record: PrevengosTrainingRecord) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/contracts/C-001":
            assert request.headers["Authorization"] == "Bearer token"
            return httpx.Response(200, json={"code": "C-001", "name": "Cliente"})
        if request.url.path == "/training-records":
            payload = json.loads(request.content)
            assert payload[0]["employee_nif"] == sample_record.employee_nif
            return httpx.Response(200, json=[{"status": "accepted"} for _ in payload])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://prevengos.local", transport=transport)
    api_client = PrevengosAPIClient(
        base_url="https://prevengos.local", token="token", client=client
    )

    contract = api_client.fetch_contract("C-001")
    assert contract["code"] == "C-001"

    response = api_client.push_training_records([sample_record])
    assert response == [{"status": "accepted"}]


def _sqlite_factory(rows: list[tuple[str, str, str, str, float, str]]):
    def factory() -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE prl_training_status (
                employee_nif TEXT,
                contract_code TEXT,
                course_code TEXT,
                status TEXT,
                hours_completed REAL,
                last_update TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO prl_training_status (
                employee_nif, contract_code, course_code, status, hours_completed, last_update
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return conn

    return factory


def test_db_adapter_fetch_records(sample_record: PrevengosTrainingRecord) -> None:
    rows = [
        (
            sample_record.employee_nif,
            sample_record.contract_code,
            sample_record.course_code,
            sample_record.status,
            sample_record.hours_completed,
            sample_record.last_update.strftime(ISO_FORMAT),
        )
    ]
    adapter = PrevengosDBAdapter(connection_factory=_sqlite_factory(rows))

    fetched = adapter.fetch_training_records()
    assert fetched[0].employee_nif == sample_record.employee_nif

    later = adapter.fetch_training_records(
        since=sample_record.last_update + timedelta(days=1)
    )
    assert later == []


def test_sync_service_reconcile_and_push(
    tmp_path: Path, sample_record: PrevengosTrainingRecord
) -> None:
    csv_path = tmp_path / "prevengos.csv"
    csv_adapter = PrevengosCSVAdapter(csv_path)

    older_record = PrevengosTrainingRecord(
        employee_nif=sample_record.employee_nif,
        contract_code=sample_record.contract_code,
        course_code=sample_record.course_code,
        status="pending",
        hours_completed=0,
        last_update=sample_record.last_update - timedelta(days=1),
    )
    csv_adapter.write_records([older_record])

    newer_rows = [
        (
            sample_record.employee_nif,
            sample_record.contract_code,
            sample_record.course_code,
            sample_record.status,
            sample_record.hours_completed,
            sample_record.last_update.strftime(ISO_FORMAT),
        )
    ]
    db_adapter = PrevengosDBAdapter(connection_factory=_sqlite_factory(newer_rows))

    responses: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/training-records":
            responses.append(
                {"path": request.url.path, "body": json.loads(request.content)}
            )
            return httpx.Response(200, json=[{"status": "accepted"}])
        raise AssertionError("Unexpected request")

    api_client = PrevengosAPIClient(
        base_url="https://prevengos.local",
        token="token",
        client=httpx.Client(base_url="https://prevengos.local", transport=httpx.MockTransport(handler)),
    )

    service = PrevengosSyncService(
        csv_adapter=csv_adapter, api_client=api_client, db_adapter=db_adapter
    )

    merged = service.reconcile_with_database()
    assert merged[0].status == "completed"

    push_response = service.export_records(merged, push_to_api=True)
    assert responses and responses[0]["body"][0]["status"] == "completed"
    assert push_response == [{"status": "accepted"}]


def test_sync_service_requires_clients(
    tmp_path: Path, sample_record: PrevengosTrainingRecord
) -> None:
    csv_adapter = PrevengosCSVAdapter(tmp_path / "missing.csv")
    service = PrevengosSyncService(csv_adapter=csv_adapter)

    with pytest.raises(PrevengosIntegrationError):
        service.export_records([sample_record], push_to_api=True)

    with pytest.raises(PrevengosIntegrationError):
        service.reconcile_with_database()

    with pytest.raises(PrevengosIntegrationError):
        service.fetch_contract_metadata("C-001")
