"""CSV adapter to import and export Prevengos training data."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List

from .exceptions import PrevengosCSVError
from .models import PrevengosTrainingRecord


class PrevengosCSVAdapter:
    """Read and write Prevengos data files with a controlled schema."""

    def __init__(self, path: Path, encoding: str = "utf-8-sig") -> None:
        self.path = Path(path)
        self.encoding = encoding
        self.fieldnames = [
            "employee_nif",
            "contract_code",
            "course_code",
            "status",
            "hours_completed",
            "last_update",
        ]

    def read_records(self) -> List[PrevengosTrainingRecord]:
        """Load records from the CSV file, returning an empty list if it does not exist."""

        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding=self.encoding, newline="") as file:
                reader = csv.DictReader(file)
                records = [PrevengosTrainingRecord.from_csv_row(row) for row in reader]
        except (OSError, ValueError, KeyError) as exc:  # pragma: no cover - defensive
            raise PrevengosCSVError(f"Unable to read Prevengos CSV: {exc}") from exc
        return records

    def write_records(self, records: Iterable[PrevengosTrainingRecord]) -> None:
        """Persist the provided records overriding the file contents."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [record.to_csv_row() for record in records]
        fieldnames = self._merge_fieldnames(rows)
        try:
            with self.path.open("w", encoding=self.encoding, newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:  # pragma: no cover - defensive
            raise PrevengosCSVError(f"Unable to write Prevengos CSV: {exc}") from exc

    def _merge_fieldnames(self, rows: List[dict]) -> List[str]:
        """Ensure dynamic fields from the `extra` payload are preserved."""

        fieldnames = list(self.fieldnames)
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        return fieldnames
