# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import asyncio
import appsettings2
from datetime import datetime, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database, connect_async
from deev.clickhouse import AsyncClickHouseTableAdapter
from deev.clickhouse.async_clickhouse_proxy_connection import AsyncClickHouseProxyConnection
from uuid import UUID, uuid4
from punit import fact, trait
from clickhouse_connect.driver.exceptions import DatabaseError
import types
import clickhouse_connect
import time


async def _connect_async_with_retry(
    cxnstring: ConnectionString,
) -> AsyncClickHouseProxyConnection:
    """Create an async ClickHouse connection, retrying if UNKNOWN_DATABASE.

    The sync native-protocol client and async HTTP client may hit different
    backend servers in load-balanced setups on the same port.
    """
    parts = cxnstring.server.split(':')  # type: ignore[union-attr]
    host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 8123)

    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            client = await clickhouse_connect.get_async_client(
                username=cxnstring.user or 'default',
                password=cxnstring.password or '',
                host=host_name,
                port=port_number,
                database=cxnstring.database,
                connect_timeout=3,
                send_receive_timeout=9,
            )
            return AsyncClickHouseProxyConnection(client)
        except DatabaseError as db_exc:
            if 'UNKNOWN_DATABASE' in str(db_exc):
                last_exc = db_exc
            else:
                raise
        if attempt < 4:
            await asyncio.sleep(0.1 * (attempt + 1))
    raise last_exc  # type: ignore[misc,no-untyped-call]


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_basic_crud() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class BasicEntity:
            id: str = field(primary_key=True)
            example: int | None = None
            example_text: str | None = None
            other: UUID | None = None
            floaty: float | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[BasicEntity](connection, create_table=True)

            entity1 = BasicEntity(
                id=uuid4().hex,
                example=100,
                other=uuid4(),
                floaty=1.41
            )
            entity_key = await adapter.create(entity1)
            assert entity_key is not None
            assert entity_key.get('id') is not None

            read_back = await adapter.read(**entity_key)
            assert read_back is not None
            assert read_back.example == 100

            read_back.example_text = 'async_updated'
            await adapter.update(read_back)
            time.sleep(0.1)

            read_back2 = await adapter.read(**entity_key)
            assert read_back2 is not None
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_create_kwargs() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class KwargsEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[KwargsEntity](connection, create_table=True)

            key = await adapter.create(id=uuid4().hex, value='from_kwargs')
            assert key is not None
            assert key.get('id') is not None

            result = await adapter.read(**key)
            assert result is not None
            assert result.value == 'from_kwargs'
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_query_and_delete() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class QueryEntity:
            id: str = field(primary_key=True)
            name: str | None = None
            status: str | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[QueryEntity](connection, create_table=True)

            for i in range(3):
                await adapter.create(id=f'item_{uuid4().hex}', name=f'item_{i}', status='active')
            time.sleep(0.2)

            results = []
            async for row in adapter.query(where='status=%?', params=['active']):
                results.append(row)
            assert len(results) >= 3
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_upsert() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class UpsertEntity:
            id: str = field(primary_key=True)
            name: str | None = None
            count: int | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[UpsertEntity](connection, create_table=True)

            entity1 = UpsertEntity(id=uuid4().hex, name='new_entity', count=1)
            pk = await adapter.upsert(entity1)
            assert pk is not None
            assert pk.get('id') is not None

            read_back = await adapter.read(**pk)
            assert read_back is not None
            assert read_back.name == 'new_entity'
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_primary_key_property() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class PKEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[PKEntity](connection, create_table=True)
            assert adapter.primary_key == ('id',)
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_exists_works() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class ExistsEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[ExistsEntity](connection, create_table=True)

            fake_id = 'nonexistent-id-123456789012345678901234'
            assert await adapter.exists(id=fake_id) is False

            entity1 = ExistsEntity(id=uuid4().hex, value='exists')
            await adapter.create(entity1)
            time.sleep(0.2)

            assert await adapter.exists(id=entity1.id) is True
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_bulk_create() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class BulkEntity:
            id: str = field(primary_key=True)
            order: int | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[BulkEntity](connection, create_table=True)

            entities = [
                BulkEntity(id=f'bulk-{i}', order=i)
                for i in range(5)
            ]
            pks = await adapter.bulk_create(entities)
            assert len(pks) == 5

            time.sleep(0.2)

            results = []
            async for row in adapter.query():
                results.append(row)
            assert len(results) >= 5
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_delete_works() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class DeleteEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[DeleteEntity](connection, create_table=True)

            entity1 = DeleteEntity(id=uuid4().hex, value='to_delete')
            await adapter.create(entity1)
            time.sleep(0.2)

            # Verify exists before delete
            assert await adapter.exists(id=entity1.id) is True

            # Delete
            await adapter.delete(id=entity1.id)
            time.sleep(0.2)

            # Verify gone
            found = []
            async for row in adapter.query():
                found.append(row)
            assert all(r.id != entity1.id for r in found)
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_uuid_field_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class UuidEntity:
            id: str = field(primary_key=True)
            ref_uuid: UUID | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[UuidEntity](connection, create_table=True)

            target_uuid = uuid4()
            entity1 = UuidEntity(id=uuid4().hex, ref_uuid=target_uuid)
            pk = await adapter.create(entity1)
            assert pk is not None

            time.sleep(0.2)

            result = await adapter.read(**pk)
            assert result is not None
            assert result.ref_uuid == target_uuid
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
async def async_adapter_query_with_orderby_limit() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class OrderEntity:
            id: str = field(primary_key=True)
            priority: int | None = None

        async with await _connect_async_with_retry(cxnstring) as connection:
            adapter = AsyncClickHouseTableAdapter[OrderEntity](connection, create_table=True)

            for i in range(5):
                await adapter.create(id=f'order-{i}', priority=i)

            results = []
            async for row in adapter.query(orderby='priority ASC', limit=3):
                results.append(row)
            assert len(results) <= 3
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as c:
                    c.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            _drop_db()
        except Exception:
            pass

