"""Tests for the external SQL bridge helpers."""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import sessionmaker

from app.integrations.sql_bridge import (
    DatabaseBridgeService,
    ExternalSQLBridgeError,
    ExternalSQLClient,
)


def _sqlite_engine(path: pathlib.Path):
    return create_engine(f"sqlite:///{path}", future=True)


def test_external_sql_client_executes_queries(tmp_path):
    engine = _sqlite_engine(tmp_path / "external.db")
    client = ExternalSQLClient(engine)

    client.execute("CREATE TABLE data (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)")
    affected = client.execute(
        "INSERT INTO data (value) VALUES (:value)", {"value": "hola"}
    )

    assert affected == 1
    rows = client.fetch_all("SELECT id, value FROM data ORDER BY id")
    assert rows == [{"id": 1, "value": "hola"}]


def test_external_sql_client_streams_results(tmp_path):
    engine = _sqlite_engine(tmp_path / "external_stream.db")
    client = ExternalSQLClient(engine)
    client.execute("CREATE TABLE payload (id INTEGER, value TEXT)")
    client.execute_many(
        "INSERT INTO payload (id, value) VALUES (:id, :value)",
        [{"id": i, "value": f"item-{i}"} for i in range(5)],
    )

    streamed = list(client.stream("SELECT id, value FROM payload ORDER BY id", chunk_size=2))
    assert streamed == [{"id": i, "value": f"item-{i}"} for i in range(5)]


def test_database_bridge_sync_query_to_external(tmp_path):
    local_engine = _sqlite_engine(tmp_path / "local.db")
    metadata = MetaData()
    source = Table(
        "source",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String(50)),
    )
    metadata.create_all(local_engine)
    SessionLocal = sessionmaker(bind=local_engine, future=True)

    with SessionLocal() as session:
        session.execute(source.insert(), [{"id": 1, "value": "uno"}, {"id": 2, "value": "dos"}])
        session.commit()

    external_engine = _sqlite_engine(tmp_path / "external_target.db")
    client = ExternalSQLClient(external_engine)
    client.execute("CREATE TABLE target (id INTEGER, value TEXT)")
    client.execute("INSERT INTO target (id, value) VALUES (99, 'legacy')")

    bridge = DatabaseBridgeService(SessionLocal, client)
    inserted = bridge.sync_query_to_external(
        select(source.c.id, source.c.value),
        target_table="target",
        truncate=True,
    )

    assert inserted == 2
    rows = client.fetch_all("SELECT id, value FROM target ORDER BY id")
    assert rows == [{"id": 1, "value": "uno"}, {"id": 2, "value": "dos"}]


def test_database_bridge_import_external(tmp_path):
    local_engine = _sqlite_engine(tmp_path / "local_import.db")
    metadata = MetaData()
    destination = Table(
        "destination",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String(50)),
    )
    metadata.create_all(local_engine)
    SessionLocal = sessionmaker(bind=local_engine, future=True)

    external_engine = _sqlite_engine(tmp_path / "external_source.db")
    client = ExternalSQLClient(external_engine)
    client.execute("CREATE TABLE source (id INTEGER, value TEXT)")
    client.execute_many(
        "INSERT INTO source (id, value) VALUES (:id, :value)",
        [{"id": 10, "value": "diez"}, {"id": 11, "value": "once"}],
    )

    bridge = DatabaseBridgeService(SessionLocal, client)

    def handler(session, row):
        session.execute(destination.insert().values(row))

    processed = bridge.import_external(
        "SELECT id, value FROM source ORDER BY id",
        handler,
        chunk_size=1,
        commit_interval=1,
    )

    assert processed == 2
    with SessionLocal() as session:
        result = session.execute(select(destination.c.id, destination.c.value).order_by(destination.c.id))
        assert result.all() == [(10, "diez"), (11, "once")]


def test_validate_identifier_rejects_invalid_names():
    with pytest.raises(ExternalSQLBridgeError):
        ExternalSQLClient.validate_identifier("invalid name")
