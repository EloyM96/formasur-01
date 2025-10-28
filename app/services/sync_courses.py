"""Service layer orchestrating Moodle synchronisation flows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.config import settings
from app.connectors.moodle import MoodleRESTClient
from app.models import CourseModel


@dataclass(slots=True)
class CourseSyncResult:
    """Value object describing the outcome of a synchronisation run."""

    courses: list[CourseModel]
    source: str
    dry_run: bool


class CourseSyncService:
    """Load courses either from XLSX exports or the Moodle API depending on flags."""

    REQUIRED_COLUMNS = ("name", "hours_required", "deadline_date")

    def __init__(
        self,
        *,
        rest_client: MoodleRESTClient | None = None,
        settings_module=settings,
    ) -> None:
        self._settings = settings_module
        self._rest_client = rest_client or self._build_rest_client(settings_module)

    @property
    def use_moodle_api(self) -> bool:
        """Return ``True`` when the Moodle API should be the primary source."""

        return bool(self._settings.moodle_api_enabled and self._rest_client)

    @property
    def dry_run(self) -> bool:
        """Expose whether downstream workflows must remain in dry-run mode."""

        return not self.use_moodle_api

    def sync(self, *, source_path: Path | None = None) -> CourseSyncResult:
        """Collect courses from the configured source and convert them to models."""

        if self.use_moodle_api:
            courses = self._from_rest_api()
            return CourseSyncResult(courses=courses, source="moodle", dry_run=self.dry_run)
        if source_path is None:
            msg = "Es necesario proporcionar el XLSX de Moodle cuando la API está deshabilitada"
            raise ValueError(msg)
        courses = self._from_xlsx(source_path)
        return CourseSyncResult(courses=courses, source="xlsx", dry_run=self.dry_run)

    def _from_rest_api(self) -> list[CourseModel]:
        assert self._rest_client is not None  # narrow type for mypy and linters
        raw_courses = self._rest_client.fetch_courses()
        return [self._map_rest_course(payload) for payload in raw_courses]

    def _from_xlsx(self, path: Path) -> list[CourseModel]:
        dataframe = pd.read_excel(path, engine="openpyxl")
        self._validate_columns(dataframe.columns)
        models: list[CourseModel] = []
        for row in dataframe.to_dict(orient="records"):
            models.append(self._map_xlsx_row(row))
        return models

    def _map_rest_course(self, payload: dict) -> CourseModel:
        name = str(payload.get("name") or payload.get("fullname") or "Curso sin nombre")
        hours_raw = payload.get("hours_required") or payload.get("hours") or 0
        deadline_raw = (
            payload.get("deadline_date")
            or payload.get("enddate")
            or payload.get("due_date")
        )
        if deadline_raw is None:
            deadline_raw = datetime.now(tz=UTC).date()
        reference = payload.get("source_reference") or payload.get("idnumber") or payload.get("id")
        created_at = self._coerce_datetime(payload.get("created_at"))
        excluded = {
            "name",
            "fullname",
            "hours_required",
            "hours",
            "deadline_date",
            "enddate",
            "due_date",
            "source_reference",
            "idnumber",
            "id",
            "created_at",
        }
        attributes = {key: value for key, value in payload.items() if key not in excluded}
        return CourseModel(
            id=None,
            name=name,
            hours_required=int(hours_raw or 0),
            deadline_date=self._coerce_date(deadline_raw),
            source="moodle",
            source_reference=str(reference or name),
            attributes=attributes or None,
            created_at=created_at,
        )

    def _map_xlsx_row(self, row: dict) -> CourseModel:
        name = str(row.get("name") or row.get("Nombre") or row.get("curso") or "Curso XLSX")
        hours = int(row.get("hours_required") or row.get("Horas") or 0)
        deadline_raw = (
            row.get("deadline_date")
            or row.get("Fecha límite")
            or row.get("deadline")
            or datetime.now(tz=UTC).date()
        )
        reference = row.get("source_reference") or row.get("reference") or name
        excluded = {
            "name",
            "Nombre",
            "curso",
            "hours_required",
            "Horas",
            "deadline_date",
            "Fecha límite",
            "deadline",
            "source_reference",
            "reference",
        }
        attributes = {key: value for key, value in row.items() if key not in excluded}
        return CourseModel(
            id=None,
            name=name,
            hours_required=hours,
            deadline_date=self._coerce_date(deadline_raw),
            source="xlsx",
            source_reference=str(reference),
            attributes=attributes or None,
            created_at=datetime.now(tz=UTC),
        )

    def _validate_columns(self, columns: Iterable[str]) -> None:
        missing = [column for column in self.REQUIRED_COLUMNS if column not in columns]
        if missing:
            msg = f"El fichero XLSX debe incluir las columnas: {', '.join(missing)}"
            raise ValueError(msg)

    def _coerce_date(self, value: object) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, pd.Timestamp):  # type: ignore[arg-type]
            return value.to_pydatetime().date()
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=UTC).date()
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return parsed.date()
        raise ValueError("No ha sido posible convertir la fecha de vencimiento del curso")

    def _coerce_datetime(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC)
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=UTC)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return datetime.now(tz=UTC)

    def _build_rest_client(self, config: object) -> MoodleRESTClient | None:
        base_url = getattr(config, "moodle_rest_base_url", None)
        token = getattr(config, "moodle_token", None)
        if not base_url or not token:
            return None
        return MoodleRESTClient(
            base_url=base_url,
            token=token,
            enabled=config.moodle_api_enabled,
        )


__all__ = ["CourseSyncResult", "CourseSyncService"]
