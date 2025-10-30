"""High level helpers to orchestrate synchronisation with external SQL stores."""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

from app.config import settings

from app.db import SessionLocal
from app.integrations.sql_bridge import DatabaseBridgeService, ExternalSQLClient


def build_external_sql_client() -> ExternalSQLClient | None:
    """Create an :class:`ExternalSQLClient` based on configuration settings."""

    if not settings.external_sql_enabled:
        return None

    if not settings.external_sql_database_url:
        raise ValueError(
            "external_sql_database_url must be configured when the bridge is enabled"
        )

    engine: Engine = create_engine(
        settings.external_sql_database_url,
        future=True,
        echo=settings.external_sql_echo,
    )
    return ExternalSQLClient(engine)


def build_database_bridge_service() -> DatabaseBridgeService | None:
    """Return a ready-to-use :class:`DatabaseBridgeService` if enabled."""

    client = build_external_sql_client()
    if client is None:
        return None
    return DatabaseBridgeService(SessionLocal, client)


__all__ = [
    "build_database_bridge_service",
    "build_external_sql_client",
    "DatabaseBridgeService",
    "ExternalSQLClient",
]
