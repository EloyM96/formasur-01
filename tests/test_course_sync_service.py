from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.services.sync_courses import CourseSyncService


class StubRESTClient:
    def __init__(self, payload):
        self.payload = payload
        self.called = False

    def fetch_courses(self):
        self.called = True
        return self.payload


@pytest.fixture()
def sample_xlsx(tmp_path: Path) -> Path:
    dataframe = pd.DataFrame(
        [
            {
                "name": "Prevención avanzada",
                "hours_required": 12,
                "deadline_date": date(2024, 6, 30),
                "modality": "online",
            }
        ]
    )
    path = tmp_path / "courses.xlsx"
    dataframe.to_excel(path, index=False)
    return path


def test_sync_service_uses_xlsx_when_api_disabled(monkeypatch, sample_xlsx: Path):
    monkeypatch.setattr(settings, "moodle_api_enabled", False, raising=False)
    service = CourseSyncService(rest_client=None, settings_module=settings)

    result = service.sync(source_path=sample_xlsx)

    assert result.source == "xlsx"
    assert result.dry_run is True
    assert result.courses[0].name == "Prevención avanzada"
    assert result.courses[0].attributes["modality"] == "online"


def test_sync_service_uses_rest_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "moodle_api_enabled", True, raising=False)
    payload = [
        {
            "fullname": "Prevención básica",
            "hours": 8,
            "enddate": 1_700_000_000,
            "id": 42,
        }
    ]
    service = CourseSyncService(rest_client=StubRESTClient(payload), settings_module=settings)

    result = service.sync()

    assert result.source == "moodle"
    assert result.dry_run is False
    assert result.courses[0].source == "moodle"
    assert result.courses[0].source_reference == "42"
    assert result.courses[0].hours_required == 8
    assert service._rest_client.called is True
