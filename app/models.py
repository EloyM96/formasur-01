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
    from sqlalchemy import (
        Date,
        DateTime,
        Float,
        ForeignKey,
        Integer,
        JSON,
        String,
        Text,
        func,
    )
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        """Declarative base for SQLAlchemy ORM models."""

    class Contact(Base):
        """Represents a unique contact that can receive communications."""

        __tablename__ = "contacts"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        full_name: Mapped[str] = mapped_column(String(255), nullable=False)
        email: Mapped[str | None] = mapped_column(
            String(255), nullable=True, unique=True
        )
        phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
        attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
        updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )

    class Course(Base):
        """Training course metadata sourced from learning platforms."""

        __tablename__ = "courses"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        name: Mapped[str] = mapped_column(String(255), nullable=False)
        hours_required: Mapped[int] = mapped_column(Integer, nullable=False)
        deadline_date: Mapped[date] = mapped_column(Date, nullable=False)
        source: Mapped[str] = mapped_column(String(50), nullable=False, default="xlsx")
        source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
        attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )

    class Student(Base):
        """Example ORM entity representing a learner enrolled in Moodle courses."""

        __tablename__ = "students"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        full_name: Mapped[str] = mapped_column(String(255), nullable=False)
        email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
        course: Mapped[str] = mapped_column(String(255), nullable=False)
        certificate_expires_at: Mapped[date] = mapped_column(Date, nullable=False)

    class Enrollment(Base):
        """Join table linking students with courses and tracking their progress."""

        __tablename__ = "enrollments"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        course_id: Mapped[int | None] = mapped_column(
            ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
        )
        student_id: Mapped[int | None] = mapped_column(
            ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
        )
        contact_id: Mapped[int | None] = mapped_column(
            ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
        )
        progress_hours: Mapped[float] = mapped_column(
            Float, nullable=False, default=0.0
        )
        status: Mapped[str] = mapped_column(
            String(50), nullable=False, default="active"
        )
        last_notified_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True
        )
        attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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
        enrollment_id: Mapped[int | None] = mapped_column(
            ForeignKey("enrollments.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )
        playbook: Mapped[str | None] = mapped_column(String(255), nullable=True)
        channel: Mapped[str] = mapped_column(String(50), nullable=False)
        adapter: Mapped[str] = mapped_column(String(100), nullable=False)
        recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
        subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
        status: Mapped[str] = mapped_column(String(50), nullable=False)
        payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
        response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        error: Mapped[str | None] = mapped_column(Text, nullable=True)
        job_id: Mapped[str | None] = mapped_column(
            String(191),
            ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
        sent_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True
        )

    class Job(Base):
        """Background job tracked for observability and correlation."""

        __tablename__ = "jobs"

        id: Mapped[str] = mapped_column(String(191), primary_key=True)
        name: Mapped[str] = mapped_column(String(255), nullable=False)
        queue_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
        status: Mapped[str] = mapped_column(
            String(50), nullable=False, default="queued"
        )
        payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
        started_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True
        )
        finished_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True
        )

    class JobEvent(Base):
        """Time-ordered events emitted while a job progresses through the pipeline."""

        __tablename__ = "job_events"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        job_id: Mapped[str] = mapped_column(
            String(191),
            ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        event_type: Mapped[str] = mapped_column(String(100), nullable=False)
        message: Mapped[str | None] = mapped_column(Text, nullable=True)
        payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )

except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    from dataclasses import dataclass

    class Base:  # type: ignore[override]
        """Placeholder base when SQLAlchemy is unavailable."""

    @dataclass
    class Contact(Base):  # type: ignore[override]
        id: int | None = None
        full_name: str = ""
        email: str | None = None
        phone: str | None = None
        attributes: dict | None = None
        created_at: datetime = datetime.utcnow()
        updated_at: datetime = datetime.utcnow()

    @dataclass
    class Course(Base):  # type: ignore[override]
        id: int | None = None
        name: str = ""
        hours_required: int = 0
        deadline_date: date = date.today()
        source: str = "xlsx"
        source_reference: str | None = None
        attributes: dict | None = None
        created_at: datetime = datetime.utcnow()

    @dataclass
    class Student(Base):  # type: ignore[override]
        id: int | None = None
        full_name: str = ""
        email: str = ""
        course: str = ""
        certificate_expires_at: date = date.today()

    @dataclass
    class Enrollment(Base):  # type: ignore[override]
        id: int | None = None
        course_id: int | None = None
        student_id: int | None = None
        contact_id: int | None = None
        progress_hours: float = 0.0
        status: str = "active"
        last_notified_at: datetime | None = None
        attributes: dict | None = None

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
        enrollment_id: int | None = None
        playbook: str | None = None
        channel: str = ""
        adapter: str = ""
        recipient: str | None = None
        subject: str | None = None
        status: str = "dry_run"
        payload: dict = None  # type: ignore[assignment]
        response: dict | None = None
        error: str | None = None
        job_id: str | None = None
        created_at: datetime = datetime.utcnow()
        sent_at: datetime | None = None

        def __post_init__(self) -> None:  # pragma: no cover - defensive defaulting
            if self.payload is None:
                self.payload = {}

    @dataclass
    class Job(Base):  # type: ignore[override]
        id: str = ""
        name: str = ""
        queue_name: str | None = None
        status: str = "queued"
        payload: dict | None = None
        created_at: datetime = datetime.utcnow()
        started_at: datetime | None = None
        finished_at: datetime | None = None

    @dataclass
    class JobEvent(Base):  # type: ignore[override]
        id: int | None = None
        job_id: str = ""
        event_type: str = ""
        message: str | None = None
        payload: dict | None = None
        created_at: datetime = datetime.utcnow()


class StudentModel(BaseModel):
    """Pydantic representation of the :class:`Student` ORM entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(
        default=None, description="Database identifier of the student"
    )
    full_name: str
    email: str
    course: str
    certificate_expires_at: date


class NotificationModel(BaseModel):
    """Pydantic representation of the :class:`Notification` audit entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Database identifier of the entry")
    enrollment_id: int | None = None
    playbook: str | None = None
    channel: str
    adapter: str
    recipient: str | None = None
    subject: str | None = None
    status: str
    payload: dict
    response: dict | None = None
    error: str | None = None
    job_id: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class ContactModel(BaseModel):
    """Pydantic representation of a contact entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    full_name: str
    email: str | None = None
    phone: str | None = None
    attributes: dict | None = None
    created_at: datetime
    updated_at: datetime


class CourseModel(BaseModel):
    """Pydantic representation of the :class:`Course` entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str
    hours_required: int
    deadline_date: date
    source: str
    source_reference: str | None = None
    attributes: dict | None = None
    created_at: datetime


class EnrollmentModel(BaseModel):
    """Pydantic representation of :class:`Enrollment`."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    course_id: int | None = None
    student_id: int | None = None
    contact_id: int | None = None
    progress_hours: float
    status: str
    last_notified_at: datetime | None = None
    attributes: dict | None = None


class JobModel(BaseModel):
    """Pydantic representation of :class:`Job`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    queue_name: str | None = None
    status: str
    payload: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobEventModel(BaseModel):
    """Pydantic representation of :class:`JobEvent`."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    job_id: str
    event_type: str
    message: str | None = None
    payload: dict | None = None
    created_at: datetime


__all__ = [
    "Base",
    "Contact",
    "ContactModel",
    "Course",
    "CourseModel",
    "Enrollment",
    "EnrollmentModel",
    "Job",
    "JobEvent",
    "JobEventModel",
    "JobModel",
    "Notification",
    "NotificationModel",
    "Student",
    "StudentModel",
    "UploadedFile",
]
