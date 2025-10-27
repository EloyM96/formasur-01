"""Workflow runner that evaluates playbooks and dispatches notifications."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from app.jobs.scheduler import QuietHours, Scheduler
from app.notify.dispatcher import EvaluatedRow, NotificationDispatcher
from app.queue import notification_queue
from app.rules.engine import RuleSet


DEFAULT_PLAYBOOKS_DIR = (
    Path(__file__).resolve().parents[2] / "workflows" / "playbooks"
)


@dataclass(slots=True)
class Playbook:
    """Parsed representation of a workflow playbook."""

    name: str
    source_path: Path
    mapping_path: Path
    ruleset_path: Path
    actions: list[dict[str, Any]]
    quiet_hours: QuietHours | None


class WorkflowRunner:
    """Load playbooks, evaluate rules and orchestrate notification dispatches."""

    def __init__(
        self,
        *,
        playbooks_dir: Path | None = None,
        queue=notification_queue,
        dispatcher_factory=None,
    ) -> None:
        self._playbooks_dir = playbooks_dir or DEFAULT_PLAYBOOKS_DIR
        self._repository_root = self._playbooks_dir.parents[1]
        self._queue = queue
        self._dispatcher_factory = dispatcher_factory or self._default_dispatcher_factory

    def run(self, playbook_name: str, *, dry_run: bool) -> dict[str, Any]:
        """Execute the requested playbook either in dry-run or live mode."""

        playbook = self._load_playbook(playbook_name)
        evaluated_rows = list(self._evaluate_rows(playbook))
        dispatcher = self._dispatcher_factory(playbook)
        summary = dispatcher.dispatch(
            evaluated_rows,
            playbook.actions,
            dry_run=dry_run,
            playbook=playbook.name,
        )

        matches = sum(channel["matches"] for channel in summary.values())
        enqueued = sum(channel["enqueued"] for channel in summary.values())

        return {
            "playbook": playbook.name,
            "mode": "dry_run" if dry_run else "execute",
            "total_rows": len(evaluated_rows),
            "matched_actions": matches,
            "enqueued_actions": enqueued,
            "summary": summary,
        }

    def _load_playbook(self, identifier: str) -> Playbook:
        path = self._resolve_playbook_path(identifier)
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        name = data.get("name") or path.stem
        actions = list(data.get("actions") or [])
        quiet_hours = self._parse_quiet_hours(data.get("quiet_hours"))

        source_info = data.get("source") or {}
        source_path = self._resolve_related_path(path, source_info.get("path"))
        mapping_path = self._resolve_related_path(path, data.get("mapping"))
        ruleset_path = self._resolve_related_path(path, data.get("ruleset"))

        return Playbook(
            name=name,
            source_path=source_path,
            mapping_path=mapping_path,
            ruleset_path=ruleset_path,
            actions=actions,
            quiet_hours=quiet_hours,
        )

    def _resolve_playbook_path(self, identifier: str) -> Path:
        filename = identifier if identifier.endswith(".yaml") else f"{identifier}.yaml"
        path = (self._playbooks_dir / filename).resolve()
        if not path.exists():
            msg = f"Playbook '{identifier}' no encontrado en {self._playbooks_dir}"
            raise FileNotFoundError(msg)
        return path

    def _resolve_related_path(self, playbook_path: Path, value: Any) -> Path:
        if value is None:
            msg = f"El playbook '{playbook_path.name}' carece de la ruta necesaria"
            raise ValueError(msg)
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        local_candidate = (playbook_path.parent / candidate).resolve()
        if local_candidate.exists():
            return local_candidate
        root_candidate = (self._repository_root / candidate).resolve()
        if root_candidate.exists():
            return root_candidate
        return local_candidate

    def _parse_quiet_hours(self, payload: Any) -> QuietHours | None:
        if not payload:
            return None
        start_raw = payload.get("start")
        end_raw = payload.get("end")
        if not start_raw or not end_raw:
            return None
        start = time.fromisoformat(str(start_raw))
        end = time.fromisoformat(str(end_raw))
        return QuietHours(start=start, end=end)

    def _evaluate_rows(self, playbook: Playbook) -> Iterable[EvaluatedRow]:
        dataframe = self._load_dataframe(playbook)
        mapping = self._load_mapping(playbook.mapping_path)
        rename_map = {value: key for key, value in mapping.get("columns", {}).items()}
        dataframe = dataframe.rename(columns=rename_map)
        ruleset = RuleSet.from_yaml(playbook.ruleset_path)

        for row in dataframe.to_dict(orient="records"):
            cleaned_row = {key: self._normalize_value(value) for key, value in row.items()}
            rule_results = ruleset.evaluate({"row": cleaned_row})
            yield EvaluatedRow(row=cleaned_row, rule_results=rule_results)

    def _load_dataframe(self, playbook: Playbook) -> pd.DataFrame:
        return pd.read_excel(playbook.source_path, engine="openpyxl")

    def _load_mapping(self, mapping_path: Path) -> dict[str, Any]:
        with mapping_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            msg = "El mapeo debe ser un objeto YAML de primer nivel"
            raise ValueError(msg)
        return data

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime().isoformat()
        if pd.isna(value):  # type: ignore[arg-type]
            return None
        return value

    def _default_dispatcher_factory(self, playbook: Playbook) -> NotificationDispatcher:
        scheduler = Scheduler(quiet_hours=playbook.quiet_hours)
        return NotificationDispatcher(queue=self._queue, scheduler=scheduler)


__all__ = ["Playbook", "WorkflowRunner"]
