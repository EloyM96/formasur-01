"""Database adapter for reading/writing Prevengos staging tables."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from typing import Callable, Iterable, List, Sequence

from .exceptions import PrevengosDatabaseError
from .models import ISO_FORMAT, PrevengosTrainingRecord

ConnectionFactory = Callable[[], object]


class PrevengosDBAdapter:
    """Execute parametrised queries against the Prevengos SQL Server database."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def fetch_training_records(
        self, *, since: datetime | None = None
    ) -> List[PrevengosTrainingRecord]:
        """Retrieve training records published by Prevengos."""

        query = (
            "SELECT employee_nif, contract_code, course_code, status, "
            "hours_completed, last_update FROM prl_training_status"
        )
        params: Sequence[object] = ()
        if since is not None:
            query += " WHERE last_update >= ?"
            params = (since.strftime(ISO_FORMAT),)

        try:
            connection = self._connection_factory()
            with closing(connection):
                cursor = connection.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - DB protection
            raise PrevengosDatabaseError(f"Prevengos DB query failed: {exc}") from exc

        records = [
            PrevengosTrainingRecord.from_payload(
                {
                    "employee_nif": row[0],
                    "contract_code": row[1],
                    "course_code": row[2],
                    "status": row[3],
                    "hours_completed": row[4],
                    "last_update": row[5],
                }
            )
            for row in rows
        ]
        return records

    def upsert_training_records(
        self, records: Iterable[PrevengosTrainingRecord]
    ) -> int:
        """Write records into a staging table authorised by Prevengos."""

        query = (
            "MERGE prl_training_status AS target "
            "USING (VALUES (?, ?, ?, ?, ?, ?)) AS source("\
            "employee_nif, contract_code, course_code, status, hours_completed, last_update"\
            ") ON (target.employee_nif = source.employee_nif "
            "AND target.contract_code = source.contract_code "
            "AND target.course_code = source.course_code) "
            "WHEN MATCHED THEN UPDATE SET status = source.status, "
            "hours_completed = source.hours_completed, last_update = source.last_update "
            "WHEN NOT MATCHED THEN INSERT (employee_nif, contract_code, course_code, status, hours_completed, last_update) "
            "VALUES (source.employee_nif, source.contract_code, source.course_code, source.status, source.hours_completed, source.last_update);"
        )

        try:
            connection = self._connection_factory()
            with closing(connection):
                cursor = connection.cursor()
                rows_affected = 0
                for record in records:
                    payload = record.to_payload()
                    params = (
                        payload["employee_nif"],
                        payload["contract_code"],
                        payload["course_code"],
                        payload["status"],
                        payload["hours_completed"],
                        payload["last_update"],
                    )
                    cursor.execute(query, params)
                    rows_affected += cursor.rowcount
                cursor.connection.commit()
        except Exception as exc:  # pragma: no cover - DB protection
            raise PrevengosDatabaseError(f"Prevengos DB upsert failed: {exc}") from exc
        return rows_affected
