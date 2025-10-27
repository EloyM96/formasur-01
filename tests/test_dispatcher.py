from datetime import datetime, time

from datetime import datetime, time

import pytest

from app.jobs.scheduler import QuietHours, Scheduler
from app.notify.dispatcher import (
    AdapterNotFoundError,
    EvaluatedRow,
    NotificationDeliveryError,
    NotificationDispatcher,
)


class StubQueue:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def enqueue(self, job_name, **options):
        self.calls.append((job_name, options))


def _build_actions():
    return [
        {
            "type": "notify",
            "channel": "whatsapp",
            "template": "aviso",
            "to": "{{ row.telefono }}",
            "when": "{{ rule_results.debe_notificar }}",
        }
    ]


def test_dispatcher_enqueues_outside_quiet_hours():
    queue = StubQueue()
    quiet_hours = QuietHours(start=time(21, 0), end=time(8, 0))
    scheduler = Scheduler(quiet_hours=quiet_hours)
    dispatcher = NotificationDispatcher(
        queue=queue,
        scheduler=scheduler,
        now_provider=lambda: datetime(2024, 1, 1, 10, 0),
    )

    evaluated = [
        EvaluatedRow(row={"telefono": "+34123456789"}, rule_results={"debe_notificar": True})
    ]

    summary = dispatcher.dispatch(evaluated, _build_actions(), dry_run=False, playbook="demo")

    assert queue.calls
    job_name, options = queue.calls[0]
    assert job_name == "app.notify.worker.dispatch"
    assert options["kwargs"]["action"]["to"] == "+34123456789"
    assert summary["whatsapp"]["matches"] == 1
    assert summary["whatsapp"]["enqueued"] == 1
    assert summary["whatsapp"]["skipped_quiet_hours"] == 0
    assert summary["whatsapp"]["errors"] == 0


def test_dispatcher_skips_during_quiet_hours():
    queue = StubQueue()
    quiet_hours = QuietHours(start=time(21, 0), end=time(8, 0))
    scheduler = Scheduler(quiet_hours=quiet_hours)
    dispatcher = NotificationDispatcher(
        queue=queue,
        scheduler=scheduler,
        now_provider=lambda: datetime(2024, 1, 1, 22, 0),
    )

    evaluated = [
        EvaluatedRow(row={"telefono": "+34123456789"}, rule_results={"debe_notificar": True})
    ]

    summary = dispatcher.dispatch(evaluated, _build_actions(), dry_run=False, playbook="demo")

    assert not queue.calls
    assert summary["whatsapp"]["matches"] == 1
    assert summary["whatsapp"]["enqueued"] == 0
    assert summary["whatsapp"]["skipped_quiet_hours"] == 1
    assert summary["whatsapp"]["errors"] == 0


def test_dispatcher_dry_run_never_touches_queue():
    queue = StubQueue()
    dispatcher = NotificationDispatcher(
        queue=queue,
        scheduler=None,
        now_provider=lambda: datetime(2024, 1, 1, 12, 0),
    )

    evaluated = [
        EvaluatedRow(row={"telefono": "+34123456789"}, rule_results={"debe_notificar": True})
    ]

    summary = dispatcher.dispatch(evaluated, _build_actions(), dry_run=True, playbook="demo")

    assert not queue.calls
    assert summary["whatsapp"]["matches"] == 1
    assert summary["whatsapp"]["enqueued"] == 0
    assert summary["whatsapp"]["skipped_quiet_hours"] == 0
    assert summary["whatsapp"]["errors"] == 0


class StubAdapter:
    def __init__(self):
        self.calls: list[dict] = []

    def send(self, payload: dict) -> dict:
        self.calls.append(payload)
        return {"delivered": True}


class FailingAdapter:
    def send(self, payload: dict) -> dict:
        raise RuntimeError("boom")


class StubAuditRepository:
    def __init__(self) -> None:
        self.entries = []

    def add(self, entry):
        self.entries.append(entry)
        return entry


def test_deliver_records_audit_and_adapter_calls():
    adapter = StubAdapter()
    repository = StubAuditRepository()
    dispatcher = NotificationDispatcher(queue=None, adapters={"sms": adapter}, audit_repository=repository)

    result = dispatcher.deliver(
        playbook="demo",
        action={"channel": "sms", "to": "+34", "body": "Hola"},
        row={"to": "+34"},
        rule_results={"ok": True},
    )

    assert result["status"] == "sent"
    assert adapter.calls
    assert repository.entries
    entry = repository.entries[0]
    assert entry.status == "sent"
    assert entry.channel == "sms"


def test_deliver_missing_adapter_raises():
    dispatcher = NotificationDispatcher(queue=None, adapters={}, audit_repository=None)

    with pytest.raises(AdapterNotFoundError):
        dispatcher.deliver(
            playbook="demo",
            action={"channel": "unknown"},
            row={},
            rule_results={},
        )


def test_deliver_records_errors():
    adapter = FailingAdapter()
    repository = StubAuditRepository()
    dispatcher = NotificationDispatcher(queue=None, adapters={"sms": adapter}, audit_repository=repository)

    with pytest.raises(NotificationDeliveryError):
        dispatcher.deliver(
            playbook="demo",
            action={"channel": "sms", "to": "+34"},
            row={},
            rule_results={},
        )

    assert repository.entries
    assert repository.entries[0].status == "error"
