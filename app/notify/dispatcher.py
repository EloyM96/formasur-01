"""Notification dispatcher that renders actions and orchestrates deliveries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Protocol
from uuid import uuid4

from app.jobs.scheduler import Scheduler
from app.logging import get_logger, job_context


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
    job_id: str | None = None
    job_name: str | None = None
    queue_name: str | None = None


class NotificationAuditRepository(Protocol):
    """Repository interface used by the dispatcher to persist audits."""

    def add(self, entry: NotificationAuditEntry) -> Any:  # pragma: no cover - protocol
        """Persist *entry* in the underlying storage backend."""


class AdapterNotFoundError(RuntimeError):
    """Raised when an action references a channel without a configured adapter."""

    def __init__(self, channel: str) -> None:
        super().__init__(
            f"No existe un adaptador configurado para el canal '{channel}'"
        )
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
        return _DotAccessor(
            {key: _wrap_template_value(val) for key, val in value.items()}
        )
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
        self._logger = get_logger(__name__)

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
                    {
                        "matches": 0,
                        "enqueued": 0,
                        "skipped_quiet_hours": 0,
                        "errors": 0,
                    },
                )
                stats["matches"] += 1
                recipient = _string_or_none(rendered_action.get("to"))

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
                            recipient=recipient,
                            subject=_string_or_none(rendered_action.get("subject")),
                            status="quiet_hours",
                            payload=self._prepare_payload(
                                playbook, rendered_action, item
                            ),
                        )
                    )
                    continue

                if self._queue is None:
                    job_id = self._generate_job_id()
                    try:
                        result = self.deliver(
                            playbook=playbook,
                            action=rendered_action,
                            row=dict(item.row),
                            rule_results=dict(item.rule_results),
                            job_id=job_id,
                            job_name=self._job_name,
                            queue_name=self._queue_label(),
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

                job_id = self._generate_job_id()
                payload = {
                    "playbook": playbook,
                    "action": rendered_action,
                    "row": dict(item.row),
                    "rule_results": dict(item.rule_results),
                    "job_id": job_id,
                }
                queue_name = self._queue_label()
                self._queue.enqueue(self._job_name, kwargs=payload, job_id=job_id)
                with job_context(
                    job_id=job_id,
                    job_name=self._job_name,
                    queue_name=queue_name,
                    channel=channel,
                ):
                    self._logger.info(
                        "notification.queue.enqueued",
                        playbook=playbook,
                        recipient=recipient,
                    )
                audit_payload = self._prepare_payload(playbook, rendered_action, item)
                audit_payload.setdefault("job_id", job_id)
                self._record_audit(
                    NotificationAuditEntry(
                        playbook=playbook,
                        channel=channel,
                        adapter=self._adapter_label(channel),
                        recipient=recipient,
                        subject=_string_or_none(rendered_action.get("subject")),
                        status="queued",
                        payload=audit_payload,
                        job_id=job_id,
                        job_name=self._job_name,
                        queue_name=queue_name,
                    )
                )
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
        job_id: str | None = None,
        job_name: str | None = None,
        queue_name: str | None = None,
    ) -> dict[str, Any]:
        """Deliver a single rendered *action* using the configured adapters."""

        channel = str(action.get("channel", "default")).lower()
        adapter = self._adapter_for_channel(channel)
        adapter_name = self._adapter_name(adapter)
        recipient = _string_or_none(action.get("to"))
        subject = _string_or_none(action.get("subject"))
        payload = self._prepare_payload(
            playbook, action, EvaluatedRow(row=row, rule_results=rule_results)
        )
        job_identifier = job_id or self._generate_job_id()
        job_label = job_name or self._job_name
        queue_label = queue_name or self._queue_label()

        with job_context(
            job_id=job_identifier,
            job_name=job_label,
            queue_name=queue_label,
            channel=channel,
            adapter=adapter_name,
        ):
            self._logger.info(
                "notification.deliver.start",
                playbook=playbook,
                dry_run=dry_run,
                recipient=recipient,
            )

            if dry_run:
                payload_with_job = dict(payload)
                payload_with_job.setdefault("job_id", job_identifier)
                self._record_audit(
                    NotificationAuditEntry(
                        playbook=playbook,
                        channel=channel,
                        adapter=adapter_name,
                        recipient=recipient,
                        subject=subject,
                        status="dry_run",
                        payload=payload_with_job,
                        job_id=job_identifier,
                        job_name=job_label,
                        queue_name=queue_label,
                    )
                )
                self._logger.info("notification.deliver.dry_run", playbook=playbook)
                return {"status": "dry_run", "response": None}

            adapter_callable = getattr(adapter, "send", None) or adapter
            try:
                response = adapter_callable(
                    {
                        "playbook": playbook,
                        "action": dict(action),
                        "context": {
                            "row": dict(row),
                            "rule_results": dict(rule_results),
                        },
                    }
                )
            except AdapterNotFoundError:
                raise
            except (
                Exception
            ) as exc:  # pragma: no cover - exercised in tests via failure
                error_message = str(exc)
                payload_with_job = dict(payload)
                payload_with_job.setdefault("job_id", job_identifier)
                self._record_audit(
                    NotificationAuditEntry(
                        playbook=playbook,
                        channel=channel,
                        adapter=adapter_name,
                        recipient=recipient,
                        subject=subject,
                        status="error",
                        payload=payload_with_job,
                        error=error_message,
                        job_id=job_identifier,
                        job_name=job_label,
                        queue_name=queue_label,
                    )
                )
                self._logger.error(
                    "notification.deliver.error",
                    playbook=playbook,
                    error=error_message,
                )
                raise NotificationDeliveryError(channel, adapter_name, exc) from exc

            response_mapping = _ensure_mapping(response)
            payload_with_job = dict(payload)
            payload_with_job.setdefault("job_id", job_identifier)
            self._record_audit(
                NotificationAuditEntry(
                    playbook=playbook,
                    channel=channel,
                    adapter=adapter_name,
                    recipient=recipient,
                    subject=subject,
                    status="sent",
                    payload=payload_with_job,
                    response=response_mapping,
                    job_id=job_identifier,
                    job_name=job_label,
                    queue_name=queue_label,
                )
            )
            self._logger.info(
                "notification.deliver.success",
                playbook=playbook,
                response_status=response_mapping.get("status"),
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
        return eval(
            expression, SAFE_EVAL_GLOBALS, locals_env
        )  # noqa: S307 - controlled

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
                        playbook,
                        action,
                        EvaluatedRow(
                            row=dict(item.row), rule_results=dict(item.rule_results)
                        ),
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

    def _queue_label(self) -> str | None:
        if self._queue is None:
            return "inline"
        return getattr(self._queue, "name", None)

    def _generate_job_id(self) -> str:
        return uuid4().hex

    @property
    def job_name(self) -> str:
        """Public accessor used by workers for logging context."""

        return self._job_name


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
