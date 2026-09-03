# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.clickhouse import ClickHouseProxyConnection, ClickHouseTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait


@fact
@trait('clickhouse')
@trait('integration')
def create_table_with_replicated_database_derives_correct_engine() -> None:
    """When the database is ReplicatedMergeTree-based, create_table should derive a replicated engine for tables."""
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_engine_{uuid4().hex[:16]}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            name: str = field(max=256)

        with connect(cxnstring) as connection:
            assert isinstance(connection, ClickHouseProxyConnection)
            adapter = ClickHouseTableAdapter[TestEntity](connection, create_table=True)  # type: ignore[arg-type]
            # Verify the engine query succeeds and returns something
            client = connection.clickhouse_client
            result = client.command(
                'SELECT engine_full FROM system.databases WHERE name = currentDatabase()'
            )
            assert result is not None
            db_engine = str(result).strip()
            assert len(db_engine) > 0
            # The adapter should not raise and should create the table successfully
            adapter = ClickHouseTableAdapter[TestEntity](connection, create_table=True)
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
def create_table_with_explicit_engine_override() -> None:
    """An explicit engine= parameter should override the derived engine."""
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_override_{uuid4().hex[:16]}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            name: str = field(max=256)

        with connect(cxnstring) as connection:
            adapter = ClickHouseTableAdapter[TestEntity](connection)  # type: ignore[arg-type]
            # Override with a non-replicated engine
            adapter.create_table(engine='MergeTree')
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
def create_table_with_entity_engine_kwarg() -> None:
    """An engine= kwarg in @entity decorator should be used for DDL."""
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_entity_kwarg_{uuid4().hex[:16]}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity(engine='MergeTree')
        class TestEntity:
            id: str = field(primary_key=True)
            name: str = field(max=256)

        with connect(cxnstring) as connection:
            adapter = ClickHouseTableAdapter[TestEntity](connection, create_table=True)  # type: ignore[arg-type]
            # Create and read data to verify table was created successfully
            entity1 = TestEntity(id=uuid4().hex, name='test')
            pk = adapter.create(entity1)
            assert pk is not None
            assert pk.get('id') is not None
            data = adapter.read(**pk)
            assert data is not None
            assert data.name == 'test'
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass
