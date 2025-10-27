from pathlib import Path

from app.notify.adapters.email_smtp import EmailSMTPAdapter


class SMTPConnectionStub:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.messages = []

    def __enter__(self) -> "SMTPConnectionStub":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message) -> None:  # type: ignore[no-untyped-def]
        self.messages.append(message)


class SMTPFactory:
    def __init__(self) -> None:
        self.instances: list[SMTPConnectionStub] = []

    def __call__(self, host: str, port: int) -> SMTPConnectionStub:
        connection = SMTPConnectionStub(host, port)
        self.instances.append(connection)
        return connection


def test_email_adapter_renders_templates(tmp_path: Path):
    templates_dir = tmp_path
    (templates_dir / "bienvenida.txt").write_text("Hola {{ context.row.name }}", encoding="utf-8")
    (templates_dir / "bienvenida.html").write_text(
        "<p>Hola {{ context.row.name }}</p>", encoding="utf-8"
    )

    smtp_factory = SMTPFactory()
    adapter = EmailSMTPAdapter(
        host="smtp.test",
        port=587,
        username="user",
        password="secret",
        from_email="notifier@example.com",
        templates_dir=templates_dir,
        smtp_factory=smtp_factory,
    )

    payload = {
        "playbook": "demo",
        "action": {
            "channel": "email",
            "template": "bienvenida",
            "to": "destinatario@example.com",
            "subject": "Hola {{ context.row.name }}",
        },
        "context": {"row": {"name": "Ana"}},
    }

    result = adapter.send(payload)

    assert result["status"] == "sent"
    assert smtp_factory.instances
    connection = smtp_factory.instances[0]
    assert connection.started_tls is True
    assert connection.logged_in == ("user", "secret")
    assert connection.messages
    message = connection.messages[0]
    assert message["To"] == "destinatario@example.com"
    assert message.get_body(preferencelist=("html",)).get_content().strip() == "<p>Hola Ana</p>"
