"""Domain models used by the Prevengos integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Tuple

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


@dataclass(slots=True)
class PrevengosTrainingRecord:
    """Represents the training status that we exchange with Prevengos."""

    employee_nif: str
    contract_code: str
    course_code: str
    status: str
    hours_completed: float
    last_update: datetime
    extra: Dict[str, Any] = field(default_factory=dict)

    def identity_key(self) -> Tuple[str, str, str]:
        """Return the unique identifier composed by employee, contract and course."""

        return self.employee_nif, self.contract_code, self.course_code

    def to_csv_row(self) -> Dict[str, str]:
        """Serialize the record into a CSV friendly dictionary."""

        row = {
            "employee_nif": self.employee_nif,
            "contract_code": self.contract_code,
            "course_code": self.course_code,
            "status": self.status,
            "hours_completed": f"{self.hours_completed:.2f}",
            "last_update": self.last_update.strftime(ISO_FORMAT),
        }
        for key, value in self.extra.items():
            row[key] = "" if value is None else str(value)
        return row

    def to_payload(self) -> Dict[str, Any]:
        """Serialize the record for JSON payloads."""

        payload: Dict[str, Any] = {
            "employee_nif": self.employee_nif,
            "contract_code": self.contract_code,
            "course_code": self.course_code,
            "status": self.status,
            "hours_completed": self.hours_completed,
            "last_update": self.last_update.strftime(ISO_FORMAT),
        }
        payload.update(self.extra)
        return payload

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "PrevengosTrainingRecord":
        """Build a record from a CSV row."""

        extra = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "employee_nif",
                "contract_code",
                "course_code",
                "status",
                "hours_completed",
                "last_update",
            }
        }
        return cls(
            employee_nif=row["employee_nif"].strip(),
            contract_code=row["contract_code"].strip(),
            course_code=row["course_code"].strip(),
            status=row["status"].strip(),
            hours_completed=float(row["hours_completed"] or 0),
            last_update=datetime.strptime(row["last_update"], ISO_FORMAT),
            extra=extra,
        )

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PrevengosTrainingRecord":
        """Build a record from a JSON payload coming from the API or DB."""

        extra = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "employee_nif",
                "contract_code",
                "course_code",
                "status",
                "hours_completed",
                "last_update",
            }
        }
        last_update_raw = payload["last_update"]
        last_update = (
            datetime.strptime(last_update_raw, ISO_FORMAT)
            if isinstance(last_update_raw, str)
            else last_update_raw
        )
        return cls(
            employee_nif=str(payload["employee_nif"]).strip(),
            contract_code=str(payload["contract_code"]).strip(),
            course_code=str(payload["course_code"]).strip(),
            status=str(payload["status"]).strip(),
            hours_completed=float(payload.get("hours_completed", 0)),
            last_update=last_update,
            extra=extra,
        )
