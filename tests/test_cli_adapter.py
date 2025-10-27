from pathlib import Path

from app.notify.adapters import CLIAdapter


def test_cli_adapter_invokes_process(tmp_path: Path):
    adapter_script = tmp_path / "adapter.py"
    adapter_script.write_text(
        "\n".join(
            [
                "import json, sys",
                "payload = json.load(sys.stdin)",
                "payload['ok'] = True",
                "json.dump(payload, sys.stdout)",
            ]
        ),
        encoding="utf-8",
    )

    adapter = CLIAdapter(command=["python", str(adapter_script)])
    response = adapter.send({"action": "send", "channel": "whatsapp"})

    assert response == {"action": "send", "channel": "whatsapp", "ok": True}
