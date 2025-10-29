"""HTTP client for the Prevengos JSON service."""

from __future__ import annotations

from typing import Iterable, List, Mapping, MutableMapping, Optional

import httpx

from .exceptions import PrevengosAPIError
from .models import PrevengosTrainingRecord


class PrevengosAPIClient:
    """Thin wrapper around the Prevengos JSON API."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._token = token

    def close(self) -> None:
        """Release underlying HTTP resources if we created the client."""

        if self._owns_client:
            self._client.close()

    def _auth_headers(self) -> MutableMapping[str, str]:
        headers: MutableMapping[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def fetch_contract(self, contract_code: str) -> Mapping[str, object]:
        """Retrieve contract metadata from Prevengos."""

        try:
            response = self._client.get(
                f"/contracts/{contract_code}", headers=self._auth_headers()
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network protection
            raise PrevengosAPIError(f"Prevengos API request failed: {exc}") from exc
        data = response.json()
        if not isinstance(data, Mapping):  # pragma: no cover - defensive
            raise PrevengosAPIError("Prevengos API returned a non-object response")
        return data

    def push_training_records(
        self, records: Iterable[PrevengosTrainingRecord]
    ) -> List[Mapping[str, object]]:
        """Send training records to Prevengos using the JSON API."""

        payload = [record.to_payload() for record in records]
        try:
            response = self._client.post(
                "/training-records",
                json=payload,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network protection
            raise PrevengosAPIError(f"Prevengos API request failed: {exc}") from exc
        data = response.json()
        if not isinstance(data, list):  # pragma: no cover - defensive
            raise PrevengosAPIError("Prevengos API returned a non-array response")
        return [record for record in data if isinstance(record, Mapping)]

    def __enter__(self) -> "PrevengosAPIClient":
        return self

    def __exit__(self, *_: object) -> Optional[bool]:
        self.close()
        return None
