"""Minimal ORM and Pydantic models used across the MVP."""
from __future__ import annotations

from datetime import date, datetime

try:  # pragma: no cover - exercised indirectly when dependency is present
    from pydantic import BaseModel, ConfigDict, Field
except ModuleNotFoundError:  # pragma: no cover - fallback for offline environments
    class ConfigDict(dict):
        """Lightweight stand-in emulating :class:`pydantic.ConfigDict`."""

    class BaseModel:  # type: ignore[override]
        """Simplified Pydantic replacement supporting ``model_validate``."""

        model_config: ConfigDict = ConfigDict()

        def __init__(self, **data):
            for field in self.__class__.__annotations__:
                setattr(self, field, data.get(field))

        @classmethod
        def model_validate(cls, obj):
            data = {}
            for field in cls.__annotations__:
                if hasattr(obj, field):
                    data[field] = getattr(obj, field)
            return cls(**data)

    def Field(default=None, **_kwargs):  # type: ignore[override]
        return default

try:  # pragma: no cover - prefer real SQLAlchemy when installed
    from sqlalchemy import Date, DateTime, Integer, JSON, String, Text, func
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        """Declarative base for SQLAlchemy ORM models."""

    class Student(Base):
        """Example ORM entity representing a learner enrolled in Moodle courses."""

        __tablename__ = "students"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        full_name: Mapped[str] = mapped_column(String(255), nullable=False)
        email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
        course: Mapped[str] = mapped_column(String(255), nullable=False)
        certificate_expires_at: Mapped[date] = mapped_column(Date, nullable=False)

    class UploadedFile(Base):
        """Metadata of files ingested through the uploads API."""

        __tablename__ = "uploaded_files"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        original_name: Mapped[str] = mapped_column(String(255), nullable=False)
        stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
        mime: Mapped[str] = mapped_column(String(255), nullable=False)
        size: Mapped[int] = mapped_column(Integer, nullable=False)

    class Notification(Base):
        """Audit trail entry for dispatched notifications."""

        __tablename__ = "notifications"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        playbook: Mapped[str | None] = mapped_column(String(255), nullable=True)
        channel: Mapped[str] = mapped_column(String(50), nullable=False)
        adapter: Mapped[str] = mapped_column(String(100), nullable=False)
        recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
        subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
        status: Mapped[str] = mapped_column(String(50), nullable=False)
        payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
        response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        error: Mapped[str | None] = mapped_column(Text, nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )

except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    from dataclasses import dataclass

    class Base:  # type: ignore[override]
        """Placeholder base when SQLAlchemy is unavailable."""

    @dataclass
    class Student(Base):  # type: ignore[override]
        id: int | None = None
        full_name: str = ""
        email: str = ""
        course: str = ""
        certificate_expires_at: date = date.today()

    @dataclass
    class UploadedFile(Base):  # type: ignore[override]
        id: int | None = None
        original_name: str = ""
        stored_path: str = ""
        mime: str = ""
        size: int = 0

    @dataclass
    class Notification(Base):  # type: ignore[override]
        id: int | None = None
        playbook: str | None = None
        channel: str = ""
        adapter: str = ""
        recipient: str | None = None
        subject: str | None = None
        status: str = "dry_run"
        payload: dict = None  # type: ignore[assignment]
        response: dict | None = None
        error: str | None = None
        created_at: datetime = datetime.utcnow()

        def __post_init__(self) -> None:  # pragma: no cover - defensive defaulting
            if self.payload is None:
                self.payload = {}


class StudentModel(BaseModel):
    """Pydantic representation of the :class:`Student` ORM entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Database identifier of the student")
    full_name: str
    email: str
    course: str
    certificate_expires_at: date


class NotificationModel(BaseModel):
    """Pydantic representation of the :class:`Notification` audit entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Database identifier of the entry")
    playbook: str | None = None
    channel: str
    adapter: str
    recipient: str | None = None
    subject: str | None = None
    status: str
    payload: dict
    response: dict | None = None
    error: str | None = None
    created_at: datetime


__all__ = [
    "Base",
    "Notification",
    "NotificationModel",
    "Student",
    "StudentModel",
    "UploadedFile",
]
