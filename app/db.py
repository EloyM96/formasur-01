"""Database bootstrap utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import Base

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _initialise_engine(database_url: str):
    """Create the SQLAlchemy engine ensuring SQLite files exist."""

    url: URL = make_url(database_url)
    connect_args: dict[str, Any] = {}

    if url.drivername.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        database = url.database
        if database and database not in {":memory:", ""}:
            db_path = Path(database)
            if not db_path.is_absolute():
                db_path = (PROJECT_ROOT / db_path).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(db_path))

    engine_kwargs: dict[str, Any] = {"future": True, "echo": False}
    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    engine = create_engine(url, **engine_kwargs)
    Base.metadata.create_all(engine)
    return engine


engine = _initialise_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Yield a database session for request lifecycle management."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
