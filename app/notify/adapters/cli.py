"""CLI adapter that invokes an external process following the JSON contract."""
from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CLIAdapter:
    """Execute CLI adapters that communicate via stdin/stdout JSON payloads."""

    command: Sequence[str]

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Serialize *payload* to stdin and return the parsed stdout response."""

        completed = subprocess.run(  # noqa: S603 - controlled command
            list(self.command),
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(completed.stdout or "{}")


__all__ = ["CLIAdapter"]
