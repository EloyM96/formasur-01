"""Minimal SOAP connector to reach Moodle's legacy services."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

from .exceptions import MoodleAPIError

_SOAP_ENVELOPE_TEMPLATE = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:core="urn:moodlewsrest">
  <soapenv:Header/>
  <soapenv:Body>
    <core:{function}>
      <core:token>{token}</core:token>
      {parameters}
    </core:{function}>
  </soapenv:Body>
</soapenv:Envelope>
""".strip()


class MoodleSOAPClient:
    """Call Moodle SOAP endpoints with token authentication."""

    def __init__(
        self,
        wsdl_url: str,
        token: str,
        *,
        enabled: bool | None = None,
        transport: httpx.Client | None = None,
    ) -> None:
        self.wsdl_url = wsdl_url
        self.token = token
        self.enabled = settings.moodle_api_enabled if enabled is None else enabled
        self._transport = transport or httpx.Client(timeout=10.0)

    def close(self) -> None:
        """Dispose the underlying HTTP transport."""

        self._transport.close()

    def call(self, function: str, **params: Any) -> httpx.Response:
        """Invoke a SOAP function returning the raw :class:`httpx.Response`."""

        self._ensure_enabled()
        body = self._build_envelope(function, params)
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        response = self._transport.post(self.wsdl_url, content=body, headers=headers)
        response.raise_for_status()
        return response

    def _build_envelope(self, function: str, params: dict[str, Any]) -> str:
        serialized_parameters = "\n".join(
            f"      <core:{key}>{value}</core:{key}>" for key, value in params.items()
        )
        return _SOAP_ENVELOPE_TEMPLATE.format(
            function=function,
            token=self.token,
            parameters=serialized_parameters,
        )

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise MoodleAPIError("El conector SOAP de Moodle está deshabilitado por feature flag")


__all__ = ["MoodleSOAPClient"]
