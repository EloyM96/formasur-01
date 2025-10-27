"""Database bootstrap utilities."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

engine = create_engine(settings.database_url, future=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Yield a database session for request lifecycle management."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
