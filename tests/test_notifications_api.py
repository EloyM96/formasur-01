from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import notifications as notifications_module
from app.models import Base, Notification


def _create_session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def test_list_notifications_filters():
    SessionFactory = _create_session_factory()

    with SessionFactory() as session:
        session.add_all(
            [
                Notification(
                    playbook="demo",
                    channel="email",
                    adapter="EmailSMTPAdapter",
                    recipient="ana@example.com",
                    subject="Hola",
                    status="sent",
                    payload={"action": {"channel": "email"}},
                    response={"status": "sent"},
                    created_at=datetime(2024, 1, 1, 10, 0),
                ),
                Notification(
                    playbook="demo",
                    channel="whatsapp",
                    adapter="WhatsAppCLIAdapter",
                    recipient="+34123",
                    subject=None,
                    status="error",
                    payload={"action": {"channel": "whatsapp"}},
                    response=None,
                    error="boom",
                    created_at=datetime(2024, 1, 2, 12, 0),
                ),
            ]
        )
        session.commit()

    with SessionFactory() as session:
        data = notifications_module.list_notifications(status="sent", session=session)
        assert data["total"] == 1
        assert data["items"][0]["channel"] == "email"

    with SessionFactory() as session:
        data = notifications_module.list_notifications(search="ana", session=session)
        assert data["total"] == 1
        assert data["items"][0]["recipient"] == "ana@example.com"

    with SessionFactory() as session:
        metadata = notifications_module.metadata(session=session)
        assert set(metadata["channels"]) == {"email", "whatsapp"}
        assert "sent" in metadata["statuses"]
