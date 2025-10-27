"""Dummy WhatsApp adapter that simulates a CLI integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import sys

from .cli import CLIAdapter

_SIMULATION_SCRIPT = """
import json, sys, uuid
payload = json.load(sys.stdin)
payload.setdefault("status", "simulated")
payload.setdefault("message_id", "cli-" + uuid.uuid4().hex)
json.dump(payload, sys.stdout)
""".strip()


@dataclass(slots=True)
class WhatsAppCLIAdapter:
    """Invoke a CLI adapter returning deterministic simulated responses."""

    cli: CLIAdapter | None = None

    def __post_init__(self) -> None:
        if self.cli is None:
            self.cli = CLIAdapter(command=[sys.executable, "-c", _SIMULATION_SCRIPT])

    def send(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        response = self.cli.send(dict(payload))  # type: ignore[arg-type]
        response.setdefault("status", "simulated")
        response.setdefault("message_id", "cli-simulated")
        return response


__all__ = ["WhatsAppCLIAdapter"]
