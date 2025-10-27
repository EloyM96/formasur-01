from app.notify.adapters.whatsapp_cli import WhatsAppCLIAdapter


class StubCLI:
    def __init__(self) -> None:
        self.payloads = []

    def send(self, payload):  # type: ignore[no-untyped-def]
        self.payloads.append(payload)
        return {"status": "ok", "message_id": "stub"}


def test_whatsapp_cli_adapter_simulates_when_cli_provided():
    cli = StubCLI()
    adapter = WhatsAppCLIAdapter(cli=cli)

    result = adapter.send({"action": {"channel": "whatsapp"}})

    assert cli.payloads
    assert result == {"status": "ok", "message_id": "stub"}


def test_whatsapp_cli_adapter_default_simulation():
    adapter = WhatsAppCLIAdapter()

    result = adapter.send({"action": {"channel": "whatsapp", "to": "+34"}})

    assert result["status"] == "simulated"
    assert "message_id" in result
