from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from app.workflows.runner import WorkflowRunner


class StubQueue:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def enqueue(self, job_name, **options):
        self.calls.append((job_name, options))


def create_playbook(tmp_path: Path) -> Path:
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        yaml.dump(
            {
                "columns": {
                    "email": "Email",
                    "telefono": "Telefono",
                    "debe_notificar": "DebeNotificar",
                }
            }
        ),
        encoding="utf-8",
    )

    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text(
        yaml.dump(
            {
                "rules": [
                    {
                        "id": "debe_notificar",
                        "description": "",
                        "when": "row['debe_notificar']",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    playbook_path = tmp_path / "demo_playbook.yaml"
    playbook_path.write_text(
        yaml.dump(
            {
                "name": "demo_playbook",
                "source": {"kind": "xlsx", "path": "dataset.xlsx"},
                "mapping": "./mapping.yaml",
                "ruleset": "./rules.yaml",
                "actions": [
                    {
                        "type": "notify",
                        "channel": "whatsapp",
                        "template": "aviso",
                        "to": "{{ row.telefono }}",
                        "when": "{{ rule_results.debe_notificar }}",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    return playbook_path


def dataframe() -> pd.DataFrame:
    data = {
        "Email": ["user@example.com"],
        "Telefono": ["+34123456789"],
        "DebeNotificar": [True],
    }
    return pd.DataFrame(data)


def test_workflow_runner_dry_run(monkeypatch, tmp_path):
    playbook_path = create_playbook(tmp_path)
    queue = StubQueue()
    runner = WorkflowRunner(playbooks_dir=tmp_path, queue=queue)
    monkeypatch.setattr(WorkflowRunner, "_load_dataframe", lambda self, _pb: dataframe())

    result = runner.run("demo_playbook", dry_run=True)

    assert result["mode"] == "dry_run"
    assert result["total_rows"] == 1
    assert result["matched_actions"] == 1
    assert result["enqueued_actions"] == 0
    assert result["summary"]["whatsapp"]["matches"] == 1
    assert queue.calls == []


def test_workflow_runner_execute(monkeypatch, tmp_path):
    playbook_path = create_playbook(tmp_path)
    queue = StubQueue()
    runner = WorkflowRunner(playbooks_dir=tmp_path, queue=queue)
    monkeypatch.setattr(WorkflowRunner, "_load_dataframe", lambda self, _pb: dataframe())

    result = runner.run("demo_playbook", dry_run=False)

    assert result["mode"] == "execute"
    assert result["enqueued_actions"] == 1
    assert queue.calls
    job_name, options = queue.calls[0]
    assert job_name == "app.notify.worker.dispatch"
    assert options["kwargs"]["action"]["channel"] == "whatsapp"
