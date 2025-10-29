"""High level orchestrator that coordinates Prevengos adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Mapping

from .api_client import PrevengosAPIClient
from .csv_adapter import PrevengosCSVAdapter
from .db_adapter import PrevengosDBAdapter
from .exceptions import PrevengosIntegrationError
from .models import PrevengosTrainingRecord


class PrevengosSyncService:
    """Synchronise training data across CSV, API and SQL Server channels."""

    def __init__(
        self,
        *,
        csv_adapter: PrevengosCSVAdapter,
        api_client: PrevengosAPIClient | None = None,
        db_adapter: PrevengosDBAdapter | None = None,
    ) -> None:
        self.csv_adapter = csv_adapter
        self.api_client = api_client
        self.db_adapter = db_adapter

    def export_records(
        self,
        records: Iterable[PrevengosTrainingRecord],
        *,
        push_to_api: bool = False,
    ) -> List[Mapping[str, object]]:
        """Write records to CSV and optionally propagate them to the API."""

        materialised_records = list(records)
        self.csv_adapter.write_records(materialised_records)
        if push_to_api:
            if not self.api_client:
                raise PrevengosIntegrationError(
                    "Cannot push to Prevengos API because no client was provided"
                )
            return self.api_client.push_training_records(materialised_records)
        return []

    def load_from_csv(self) -> List[PrevengosTrainingRecord]:
        """Return the cached CSV state."""

        return self.csv_adapter.read_records()

    def reconcile_with_database(
        self, *, since: datetime | None = None
    ) -> List[PrevengosTrainingRecord]:
        """Refresh the CSV file with the latest snapshot from the database."""

        if not self.db_adapter:
            raise PrevengosIntegrationError(
                "Cannot reconcile Prevengos database without a DB adapter"
            )
        current_records = {
            record.identity_key(): record for record in self.csv_adapter.read_records()
        }
        db_records = self.db_adapter.fetch_training_records(since=since)
        changed = False
        for record in db_records:
            key = record.identity_key()
            existing = current_records.get(key)
            if existing is None or record.last_update > existing.last_update:
                current_records[key] = record
                changed = True
        if changed:
            self.csv_adapter.write_records(current_records.values())
        return list(current_records.values())

    def fetch_contract_metadata(self, contract_code: str) -> Mapping[str, object]:
        """Proxy metadata requests to the Prevengos API."""

        if not self.api_client:
            raise PrevengosIntegrationError(
                "Cannot fetch Prevengos contract metadata without an API client"
            )
        return self.api_client.fetch_contract(contract_code)

    def close(self) -> None:
        """Close any owned resources."""

        if self.api_client:
            self.api_client.close()
