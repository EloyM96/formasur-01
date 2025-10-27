from __future__ import annotations

from app.api import workflows as workflows_module


class StubRunner:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[tuple[str, bool]] = []

    def run(self, playbook_name: str, *, dry_run: bool) -> dict:
        self.calls.append((playbook_name, dry_run))
        data = dict(self.payload)
        data.update({"playbook": playbook_name, "mode": "dry_run" if dry_run else "execute"})
        return data


def test_dry_run_endpoint(monkeypatch):
    payload = {"total_rows": 0, "matched_actions": 0, "enqueued_actions": 0, "summary": {}}
    runner = StubRunner(payload)
    monkeypatch.setattr(workflows_module, "workflow_runner", runner)

    response = workflows_module.dry_run("demo")

    assert runner.calls == [("demo", True)]
    assert response["mode"] == "dry_run"


def test_execute_endpoint(monkeypatch):
    payload = {"total_rows": 0, "matched_actions": 0, "enqueued_actions": 0, "summary": {}}
    runner = StubRunner(payload)
    monkeypatch.setattr(workflows_module, "workflow_runner", runner)

    response = workflows_module.execute("demo")

    assert runner.calls == [("demo", False)]
    assert response["mode"] == "execute"
