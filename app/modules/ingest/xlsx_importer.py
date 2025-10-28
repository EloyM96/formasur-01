"""Helpers to validate and preview Moodle PRL XLSX uploads."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

try:  # pragma: no cover - dependency available in production environments
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback for offline test envs
    yaml = None


DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[3] / "workflows" / "mappings" / "moodle_prl.yaml"


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


def parse_xlsx(
    file_path: Path,
    *,
    mapping_path: Path | None = None,
    preview_rows: int = 5,
) -> ImportSummary:
    """Load a spreadsheet, validate required columns and produce a preview."""

    effective_mapping_path = mapping_path or DEFAULT_MAPPING_PATH
    mapping = _load_mapping(effective_mapping_path)
    expected_columns = list((mapping.get("columns") or {}).values())

    dataframe = pd.read_excel(file_path, engine="openpyxl")

    missing_columns = [column for column in expected_columns if column not in dataframe.columns]

    errors: list[str] = []
    if missing_columns:
        errors.append("Columnas faltantes: " + ", ".join(missing_columns))

    preview = dataframe.head(preview_rows).to_dict(orient="records")

    return ImportSummary(
        total_rows=len(dataframe.index),
        missing_columns=missing_columns,
        preview=preview,
        errors=errors,
    )


def load_mapping(mapping_path: Path | None = None) -> dict[str, Any]:
    """Expose mapping loading for consumers that need to read full datasets."""

    effective_mapping_path = mapping_path or DEFAULT_MAPPING_PATH
    return _load_mapping(effective_mapping_path)


__all__ = ["ImportSummary", "parse_xlsx", "load_mapping"]
