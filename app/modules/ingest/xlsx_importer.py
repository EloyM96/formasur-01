"""Helpers to validate and preview Moodle PRL XLSX uploads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zipfile import BadZipFile

import pandas as pd

try:  # pragma: no cover - dependency available in production environments
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback for offline test envs
    yaml = None

try:  # pragma: no cover - openpyxl provides this in production
    from openpyxl.utils.exceptions import InvalidFileException
except ImportError:  # pragma: no cover - degrade gracefully if openpyxl missing
    class InvalidFileException(Exception):
        """Fallback placeholder when ``openpyxl`` is not installed."""


from ...logging import get_logger


DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[3] / "workflows" / "mappings" / "moodle_prl.yaml"


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ColumnConfig:
    """Definition of how to extract a normalized field from the spreadsheet."""

    sources: tuple[str, ...]
    required: bool


@dataclass(slots=True)
class ImportSummary:
    """Aggregate information extracted from an uploaded spreadsheet."""

    total_rows: int
    missing_columns: list[str]
    preview: list[dict[str, Any]]
    errors: list[str]

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when the spreadsheet passed all validations."""

        return not self.errors


def _load_mapping(mapping_path: Path) -> dict[str, Any]:
    if yaml is None:  # pragma: no cover - ensures graceful failure when PyYAML missing
        msg = "PyYAML es necesario para cargar el fichero de mapeos"
        raise RuntimeError(msg)

    with mapping_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise ValueError("El mapeo YAML debe ser un objeto de primer nivel")

    return data


def _coerce_column_config(raw_value: Any) -> ColumnConfig:
    if isinstance(raw_value, str):
        return ColumnConfig(sources=(raw_value,), required=True)

    if isinstance(raw_value, dict):
        sources: Iterable[str] | None = raw_value.get("sources")
        source = raw_value.get("source")
        if sources is None and source:
            sources = (source,)
        if isinstance(sources, str):  # pragma: no cover - defensive
            sources = (sources,)
        if sources is None:
            sources = tuple()
        required = raw_value.get("required")
        if required is None:
            required = bool(tuple(sources))
        return ColumnConfig(sources=tuple(sources), required=bool(required))

    return ColumnConfig(sources=tuple(), required=False)


def _resolve_mapping(raw_mapping: dict[str, Any]) -> dict[str, Any]:
    columns = raw_mapping.get("columns") or {}
    resolved_columns = {key: _coerce_column_config(value) for key, value in columns.items()}
    return {
        **raw_mapping,
        "columns": resolved_columns,
    }


def _format_preview_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def parse_xlsx(
    file_path: Path,
    *,
    mapping_path: Path | None = None,
    preview_rows: int = 5,
) -> ImportSummary:
    """Load a spreadsheet, validate required columns and produce a preview."""

    mapping = load_mapping(mapping_path)
    sheet_name = mapping.get("sheet_name")
    context = {
        "file_path": str(file_path),
        "mapping_path": str(mapping_path or DEFAULT_MAPPING_PATH),
        "sheet_name": sheet_name if sheet_name is not None else 0,
    }

    logger.info("ingest.xlsx.parse.start", **context)

    try:
        dataframe = pd.read_excel(
            file_path,
            engine="openpyxl",
            sheet_name=sheet_name if sheet_name is not None else 0,
        )
    except ValueError as exc:
        error = f"No se pudo leer la pestaña '{sheet_name}' del XLSX: {exc}"
        logger.error("ingest.xlsx.parse.failed", error=str(exc), **context)
        return ImportSummary(total_rows=0, missing_columns=[], preview=[], errors=[error])
    except (OSError, BadZipFile, InvalidFileException, ImportError) as exc:
        error = (
            "No se pudo abrir el fichero XLSX. Verifica que el archivo no está corrupto "
            f"y que utiliza un formato Excel válido. Detalle: {exc}"
        )
        logger.error("ingest.xlsx.parse.failed", error=str(exc), **context)
        return ImportSummary(total_rows=0, missing_columns=[], preview=[], errors=[error])

    column_configs: dict[str, ColumnConfig] = mapping.get("columns", {})

    required_sources: list[str] = []
    for config in column_configs.values():
        if not config.required:
            continue
        required_sources.extend(config.sources)

    missing_columns = [
        column for column in required_sources if column not in dataframe.columns
    ]

    errors: list[str] = []
    if missing_columns:
        errors.append("Columnas faltantes: " + ", ".join(missing_columns))

    preview_columns: list[str] = []
    for config in column_configs.values():
        for column in config.sources:
            if column in dataframe.columns and column not in preview_columns:
                preview_columns.append(column)

    preview_df = dataframe.head(preview_rows)
    if preview_columns:
        preview_df = preview_df.loc[:, preview_columns]
    preview_df = preview_df.fillna("")
    preview = preview_df.map(_format_preview_value).to_dict(orient="records")

    summary = ImportSummary(
        total_rows=len(dataframe.index),
        missing_columns=missing_columns,
        preview=preview,
        errors=errors,
    )

    if summary.errors:
        logger.warning(
            "ingest.xlsx.parse.invalid",
            missing_columns=summary.missing_columns,
            errors=summary.errors,
            total_rows=summary.total_rows,
            **context,
        )
    else:
        logger.info(
            "ingest.xlsx.parse.completed",
            total_rows=summary.total_rows,
            preview_rows=len(summary.preview),
            missing_columns=len(summary.missing_columns),
            **context,
        )

    return summary


def load_mapping(mapping_path: Path | None = None) -> dict[str, Any]:
    """Expose mapping loading for consumers that need to read full datasets."""

    effective_mapping_path = mapping_path or DEFAULT_MAPPING_PATH
    raw_mapping = _load_mapping(effective_mapping_path)
    return _resolve_mapping(raw_mapping)


__all__ = ["ColumnConfig", "ImportSummary", "parse_xlsx", "load_mapping"]
