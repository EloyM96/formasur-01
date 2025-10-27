"""Notification dispatcher that routes evaluated rules to the background queue."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from app.jobs.scheduler import Scheduler


SAFE_EVAL_GLOBALS = {"__builtins__": {}}
SAFE_EVAL_LOCALS = {"len": len, "str": str, "int": int, "float": float, "bool": bool}


@dataclass(slots=True)
class EvaluatedRow:
    """Represents a row of data alongside its evaluated rule results."""

    row: Mapping[str, Any]
    rule_results: Mapping[str, Any]


class _DotAccessor(dict):
    """Dictionary wrapper that exposes keys via attribute access for templates."""

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - trivial
        try:
            value = self[item]
        except KeyError as exc:  # pragma: no cover - surfacing attribute errors
            raise AttributeError(item) from exc
        return _wrap_template_value(value)


def _wrap_template_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _DotAccessor({key: _wrap_template_value(val) for key, val in value.items()})
    if isinstance(value, list):
        return [
            _wrap_template_value(item) if isinstance(item, (dict, list)) else item
            for item in value
        ]
    return value


class NotificationDispatcher:
    """Prepare and enqueue notification jobs honouring quiet hours."""

    def __init__(
        self,
        *,
        queue,
        scheduler: Scheduler | None = None,
        job_name: str = "app.notify.worker.dispatch",
        now_provider: callable = datetime.utcnow,
    ) -> None:
        self._queue = queue
        self._scheduler = scheduler
        self._job_name = job_name
        self._now = now_provider

    def dispatch(
        self,
        evaluated_rows: Iterable[EvaluatedRow],
        actions: Iterable[Mapping[str, Any]],
        *,
        dry_run: bool,
        playbook: str | None = None,
    ) -> dict[str, dict[str, int]]:
        """Dispatch notification actions to the queue and return per-channel stats."""

        summary: dict[str, dict[str, int]] = {}
        for item in evaluated_rows:
            context = {
                "row": _wrap_template_value(dict(item.row)),
                "rule_results": _wrap_template_value(dict(item.rule_results)),
            }
            for action in actions:
                if (action.get("type") or "").lower() != "notify":
                    continue
                if not self._should_dispatch(action.get("when"), context):
                    continue

                rendered_action = self._render_action(action, context)
                channel = str(rendered_action.get("channel", "default"))
                stats = summary.setdefault(
                    channel,
                    {"matches": 0, "enqueued": 0, "skipped_quiet_hours": 0},
                )
                stats["matches"] += 1

                if dry_run:
                    continue

                if (
                    self._scheduler
                    and self._scheduler.quiet_hours
                    and not self._scheduler.quiet_hours.allows(self._now())
                ):
                    stats["skipped_quiet_hours"] += 1
                    continue

                payload = {
                    "playbook": playbook,
                    "action": rendered_action,
                    "row": dict(item.row),
                    "rule_results": dict(item.rule_results),
                }
                self._queue.enqueue(self._job_name, kwargs=payload)
                stats["enqueued"] += 1
        return summary

    def _should_dispatch(self, condition: Any, context: Mapping[str, Any]) -> bool:
        if condition is None:
            return True
        if isinstance(condition, str):
            expression = condition.strip()
            if not expression:
                return True
            if expression.startswith("{{") and expression.endswith("}}"):
                expression = expression[2:-2].strip()
            value = self._eval_expression(expression, context)
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"", "false", "0", "no"}:
                    return False
                if lowered in {"true", "1", "yes"}:
                    return True
            return bool(value)
        return bool(condition)

    def _eval_expression(self, expression: str, context: Mapping[str, Any]) -> Any:
        if not expression:
            return True
        locals_env = {**SAFE_EVAL_LOCALS, **context}
        return eval(expression, SAFE_EVAL_GLOBALS, locals_env)  # noqa: S307 - controlled

    def _render_action(
        self, action: Mapping[str, Any], context: Mapping[str, Any]
    ) -> dict[str, Any]:
        rendered: dict[str, Any] = {}
        for key, value in action.items():
            if key == "when":
                continue
            if isinstance(value, str):
                rendered[key] = self._render_template(value, context)
            else:
                rendered[key] = value
        return rendered

    def _render_template(self, template: str, context: Mapping[str, Any]) -> str:
        result = template
        start = result.find("{{")
        while start != -1:
            end = result.find("}}", start)
            if end == -1:
                break
            expression = result[start + 2 : end].strip()
            value = self._eval_expression(expression, context)
            replacement = "" if value is None else str(value)
            result = result[:start] + replacement + result[end + 2 :]
            start = result.find("{{", start + len(replacement))
        return result


__all__ = ["EvaluatedRow", "NotificationDispatcher"]
