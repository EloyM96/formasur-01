"""Notification dispatcher that renders actions and orchestrates deliveries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Protocol

from app.jobs.scheduler import Scheduler


SAFE_EVAL_GLOBALS = {"__builtins__": {}}
SAFE_EVAL_LOCALS = {"len": len, "str": str, "int": int, "float": float, "bool": bool}


@dataclass(slots=True)
class EvaluatedRow:
    """Represents a row of data alongside its evaluated rule results."""

    row: Mapping[str, Any]
    rule_results: Mapping[str, Any]


@dataclass(slots=True)
class NotificationAuditEntry:
    """Structured payload used to persist notification audit traces."""

    playbook: str | None
    channel: str
    adapter: str
    recipient: str | None
    subject: str | None
    status: str
    payload: dict[str, Any]
    response: dict[str, Any] | None = None
    error: str | None = None


class NotificationAuditRepository(Protocol):
    """Repository interface used by the dispatcher to persist audits."""

    def add(self, entry: NotificationAuditEntry) -> Any:  # pragma: no cover - protocol
        """Persist *entry* in the underlying storage backend."""


class AdapterNotFoundError(RuntimeError):
    """Raised when an action references a channel without a configured adapter."""

    def __init__(self, channel: str) -> None:
        super().__init__(f"No existe un adaptador configurado para el canal '{channel}'")
        self.channel = channel


class NotificationDeliveryError(RuntimeError):
    """Raised when an adapter fails to deliver a notification."""

    def __init__(self, channel: str, adapter: str, error: Exception) -> None:
        message = f"Error al entregar la notificación por '{channel}' usando '{adapter}': {error}"
        super().__init__(message)
        self.channel = channel
        self.adapter = adapter
        self.original_error = error


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


def _ensure_serializable(value: Any) -> Any:
    """Best effort conversion to JSON-compatible data structures."""

    if isinstance(value, Mapping):
        return {str(key): _ensure_serializable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_ensure_serializable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class NotificationDispatcher:
    """Prepare jobs and route notifications to the appropriate adapters."""

    def __init__(
        self,
        *,
        queue=None,
        scheduler: Scheduler | None = None,
        adapters: Mapping[str, Any] | None = None,
        audit_repository: NotificationAuditRepository | None = None,
        job_name: str = "app.notify.worker.dispatch",
        now_provider: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        self._queue = queue
        self._scheduler = scheduler
        self._adapters = {k.lower(): v for k, v in (adapters or {}).items()}
        self._audit_repository = audit_repository
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
        """Dispatch notification actions and return per-channel stats."""

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
                channel = str(rendered_action.get("channel", "default")).lower()
                stats = summary.setdefault(
                    channel,
                    {"matches": 0, "enqueued": 0, "skipped_quiet_hours": 0, "errors": 0},
                )
                stats["matches"] += 1

                if dry_run:
                    self._record_dry_run(playbook, rendered_action, item)
                    continue

                if (
                    self._scheduler
                    and self._scheduler.quiet_hours
                    and not self._scheduler.quiet_hours.allows(self._now())
                ):
                    stats["skipped_quiet_hours"] += 1
                    self._record_audit(
                        NotificationAuditEntry(
                            playbook=playbook,
                            channel=channel,
                            adapter=self._adapter_label(channel),
                            recipient=_string_or_none(rendered_action.get("to")),
                            subject=_string_or_none(rendered_action.get("subject")),
                            status="quiet_hours",
                            payload=self._prepare_payload(playbook, rendered_action, item),
                        )
                    )
                    continue

                if self._queue is None:
                    try:
                        result = self.deliver(
                            playbook=playbook,
                            action=rendered_action,
                            row=dict(item.row),
                            rule_results=dict(item.rule_results),
                            dry_run=False,
                        )
                    except (AdapterNotFoundError, NotificationDeliveryError):
                        stats["errors"] += 1
                        continue
                    if result.get("status") == "sent":
                        stats["enqueued"] += 1
                    elif result.get("status") == "error":
                        stats["errors"] += 1
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

    def deliver(
        self,
        *,
        playbook: str | None,
        action: Mapping[str, Any],
        row: Mapping[str, Any],
        rule_results: Mapping[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Deliver a single rendered *action* using the configured adapters."""

        channel = str(action.get("channel", "default")).lower()
        adapter = self._adapter_for_channel(channel)
        adapter_name = self._adapter_name(adapter)
        recipient = _string_or_none(action.get("to"))
        subject = _string_or_none(action.get("subject"))
        payload = self._prepare_payload(playbook, action, EvaluatedRow(row=row, rule_results=rule_results))

        if dry_run:
            self._record_audit(
                NotificationAuditEntry(
                    playbook=playbook,
                    channel=channel,
                    adapter=adapter_name,
                    recipient=recipient,
                    subject=subject,
                    status="dry_run",
                    payload=payload,
                )
            )
            return {"status": "dry_run", "response": None}

        adapter_callable = getattr(adapter, "send", None) or adapter
        try:
            response = adapter_callable(
                {
                    "playbook": playbook,
                    "action": dict(action),
                    "context": {"row": dict(row), "rule_results": dict(rule_results)},
                }
            )
        except AdapterNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - exercised in tests via failure
            error_message = str(exc)
            self._record_audit(
                NotificationAuditEntry(
                    playbook=playbook,
                    channel=channel,
                    adapter=adapter_name,
                    recipient=recipient,
                    subject=subject,
                    status="error",
                    payload=payload,
                    error=error_message,
                )
            )
            raise NotificationDeliveryError(channel, adapter_name, exc) from exc

        response_mapping = _ensure_mapping(response)
        self._record_audit(
            NotificationAuditEntry(
                playbook=playbook,
                channel=channel,
                adapter=adapter_name,
                recipient=recipient,
                subject=subject,
                status="sent",
                payload=payload,
                response=response_mapping,
            )
        )
        return {"status": "sent", "response": response_mapping}

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

    def _adapter_for_channel(self, channel: str) -> Any:
        if channel == "":
            channel = "default"
        adapter = self._adapters.get(channel) if self._adapters else None
        if adapter is None:
            raise AdapterNotFoundError(channel)
        return adapter

    def _adapter_name(self, adapter: Any) -> str:
        return getattr(adapter, "name", adapter.__class__.__name__)

    def _adapter_label(self, channel: str) -> str:
        if not self._adapters:
            return channel
        adapter = self._adapters.get(channel)
        return self._adapter_name(adapter) if adapter else channel

    def _record_audit(self, entry: NotificationAuditEntry) -> None:
        if self._audit_repository is None:
            return
        self._audit_repository.add(entry)

    def _record_dry_run(
        self, playbook: str | None, action: Mapping[str, Any], item: EvaluatedRow
    ) -> None:
        if self._audit_repository is None:
            return
        try:
            self.deliver(
                playbook=playbook,
                action=action,
                row=dict(item.row),
                rule_results=dict(item.rule_results),
                dry_run=True,
            )
        except AdapterNotFoundError:
            channel = str(action.get("channel", "default")).lower()
            self._record_audit(
                NotificationAuditEntry(
                    playbook=playbook,
                    channel=channel,
                    adapter=self._adapter_label(channel),
                    recipient=_string_or_none(action.get("to")),
                    subject=_string_or_none(action.get("subject")),
                    status="dry_run",
                    payload=self._prepare_payload(
                        playbook, action, EvaluatedRow(row=dict(item.row), rule_results=dict(item.rule_results))
                    ),
                    error="adaptador no configurado",
                )
            )

    def _prepare_payload(
        self, playbook: str | None, action: Mapping[str, Any], item: EvaluatedRow
    ) -> dict[str, Any]:
        raw_payload = {
            "playbook": playbook,
            "action": dict(action),
            "row": dict(item.row),
            "rule_results": dict(item.rule_results),
        }
        return _ensure_serializable(raw_payload)


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _ensure_serializable(val) for key, val in value.items()}
    if value is None:
        return {}
    msg = "Los adaptadores deben devolver un diccionario serializable"
    raise TypeError(msg)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "AdapterNotFoundError",
    "EvaluatedRow",
    "NotificationAuditEntry",
    "NotificationAuditRepository",
    "NotificationDeliveryError",
    "NotificationDispatcher",
]
