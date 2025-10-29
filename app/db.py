"""Database bootstrap utilities."""
from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (and cache) the SQLAlchemy engine for the configured database."""

    try:
        return create_engine(settings.database_url, future=True, echo=False)
    except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard for env issues
        if exc.name == "pyodbc":
            msg = (
                "pyodbc is required to connect to SQL Server. "
                "Install the ODBC driver and the pyodbc package before running the app."
            )
            raise RuntimeError(msg) from exc
        raise


def _get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def create_session() -> Session:
    """Return a new database session bound to the configured engine."""

    factory = _get_session_factory()
    return factory()


SessionLocal = create_session


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for request lifecycle management."""

    db = create_session()
    try:
        yield db
    finally:
        db.close()


__all__ = ["create_session", "get_engine", "get_session", "SessionLocal"]
