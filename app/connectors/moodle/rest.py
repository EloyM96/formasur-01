"""Lightweight REST client tailored for Moodle's core web services."""

from __future__ import annotations

from typing import Any, Iterable

import httpx

from app.config import settings

from .exceptions import MoodleAPIError


class MoodleRESTClient:
    """Consume Moodle's REST API using token-based authentication."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        enabled: bool | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.enabled = settings.moodle_api_enabled if enabled is None else enabled
        self._http_client = http_client or httpx.Client(base_url=self.base_url, timeout=10.0)

    def close(self) -> None:
        """Release the underlying HTTP client resources."""

        self._http_client.close()

    def fetch_courses(self, *, criteria: Iterable[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Return the raw course payload produced by ``core_course_get_courses``."""

        self._ensure_enabled()
        endpoint = "/webservice/rest/server.php"
        params: dict[str, Any] = {
            "wstoken": self.token,
            "wsfunction": "core_course_get_courses",
            "moodlewsrestformat": "json",
        }
        if criteria:
            for index, item in enumerate(criteria):
                params[f"criteria[{index}][key]"] = item.get("key")
                params[f"criteria[{index}][value]"] = item.get("value")
        response = self._http_client.get(endpoint, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("exception"):
            raise MoodleAPIError(payload.get("message", "Error devuelto por Moodle"))
        if not isinstance(payload, list):
            msg = "La API REST de Moodle devolvió un formato inesperado"
            raise MoodleAPIError(msg)
        return payload

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise MoodleAPIError("El conector de Moodle está deshabilitado por feature flag")


__all__ = ["MoodleRESTClient"]
