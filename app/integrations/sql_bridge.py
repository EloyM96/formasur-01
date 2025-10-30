"""Utilities to communicate with external SQL databases using raw SQL statements.

The bridge is intentionally lightweight so that the project can exchange data with
"pure" SQL deployments managed outside of SQLAlchemy/Alembic.  It exposes a small
client for executing SQL strings and a service layer that can orchestrate data
movements between the ORM models used in this repository and external tables.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
import re
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class ExternalSQLBridgeError(RuntimeError):
    """Raised when the external SQL bridge cannot execute an operation."""


class ExternalSQLClient:
    """Thin wrapper around :func:`sqlalchemy.create_engine` for raw SQL usage.

    The client keeps the SQLAlchemy abstractions to benefit from its connection
    pooling while exposing an API oriented to string-based SQL statements so it
    can talk to databases that are managed manually.
    """

    _IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")

    def __init__(
        self,
        engine: Engine,
    ) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        """Return the underlying SQLAlchemy engine."""

        return self._engine

    def dispose(self) -> None:
        """Dispose the underlying engine, closing all pooled connections."""

        self._engine.dispose()

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Context manager that yields a raw connection."""

        with self._engine.connect() as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Context manager that yields a transactional connection."""

        with self._engine.begin() as connection:
            yield connection

    def execute(self, sql: str, parameters: Mapping[str, Any] | None = None) -> int:
        """Execute a SQL command and return the number of affected rows."""

        try:
            with self.transaction() as connection:
                result: Result[Any] = connection.execute(
                    text(sql),
                    parameters or {},
                )
        except SQLAlchemyError as exc:  # pragma: no cover - defensive, re-raised
            raise ExternalSQLBridgeError(str(exc)) from exc
        return result.rowcount

    def execute_many(
        self,
        sql: str,
        parameters: Sequence[Mapping[str, Any]] | None = None,
    ) -> int:
        """Execute a parametrised statement against a sequence of mappings."""

        payload: list[Mapping[str, Any]] = list(parameters or [])
        if not payload:
            return 0
        try:
            with self.transaction() as connection:
                result: Result[Any] = connection.execute(text(sql), payload)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive, re-raised
            raise ExternalSQLBridgeError(str(exc)) from exc
        return result.rowcount

    def fetch_all(
        self, sql: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read query and return a list of dictionaries."""

        try:
            with self.connect() as connection:
                result = connection.execute(text(sql), parameters or {})
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as exc:  # pragma: no cover - defensive, re-raised
            raise ExternalSQLBridgeError(str(exc)) from exc

    def stream(
        self,
        sql: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        chunk_size: int = 500,
    ) -> Iterable[dict[str, Any]]:
        """Yield rows lazily to operate on large result sets."""

        try:
            with self.connect() as connection:
                result = connection.execution_options(stream_results=True).execute(
                    text(sql), parameters or {}
                )
                while True:
                    chunk = result.fetchmany(chunk_size)
                    if not chunk:
                        break
                    for row in chunk:
                        yield dict(row._mapping)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive, re-raised
            raise ExternalSQLBridgeError(str(exc)) from exc

    @classmethod
    def validate_identifier(cls, identifier: str) -> str:
        """Validate a SQL identifier used in dynamic statements."""

        if not cls._IDENTIFIER_RE.match(identifier):
            msg = (
                "SQL identifiers must start with a letter/underscore and contain "
                "only alphanumeric characters, underscores or schema separators."
            )
            raise ExternalSQLBridgeError(msg)
        return identifier


class DatabaseBridgeService:
    """Service that coordinates data flow between the ORM and raw SQL targets."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        external_client: ExternalSQLClient,
    ) -> None:
        self._session_factory = session_factory
        self._external_client = external_client

    def sync_query_to_external(
        self,
        query,
        *,
        target_table: str,
        truncate: bool = False,
    ) -> int:
        """Materialise the results of a SQLAlchemy query into an external table."""

        table_name = ExternalSQLClient.validate_identifier(target_table)

        session = self._session_factory()
        try:
            result = session.execute(query)
            column_keys = list(result.keys())
            rows = result.mappings().all()
        finally:
            session.close()

        if truncate:
            self._external_client.execute(f"DELETE FROM {table_name}")

        if not rows:
            return 0

        placeholders = ", ".join(f":{column}" for column in column_keys)
        columns = ", ".join(column_keys)
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        return self._external_client.execute_many(insert_sql, rows)

    def import_external(
        self,
        sql: str,
        handler: Callable[[Session, Mapping[str, Any]], None],
        *,
        chunk_size: int = 500,
        commit_interval: int = 1000,
    ) -> int:
        """Run a raw SQL query and apply a handler for each resulting row.

        The handler receives the active ORM session so it can upsert data into the
        internal models. Commits are batched to reduce round-trips to the local
        database but still allow deterministic persistence.
        """

        if commit_interval <= 0:
            raise ValueError("commit_interval must be greater than zero")

        processed = 0
        session = self._session_factory()
        try:
            for row in self._external_client.stream(sql, chunk_size=chunk_size):
                handler(session, row)
                processed += 1
                if processed % commit_interval == 0:
                    session.commit()
            session.commit()
        finally:
            session.close()
        return processed
