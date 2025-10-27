"""Minimal ORM and Pydantic models used across the MVP."""
from __future__ import annotations

from datetime import date

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
    from sqlalchemy import Date, Integer, String
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


class StudentModel(BaseModel):
    """Pydantic representation of the :class:`Student` ORM entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Database identifier of the student")
    full_name: str
    email: str
    course: str
    certificate_expires_at: date


__all__ = ["Base", "Student", "StudentModel"]
