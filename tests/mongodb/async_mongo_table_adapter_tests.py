# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field
from deev.mongodb.async_mongo_table_adapter import AsyncMongoTableAdapter
from deev.utils import connect, connect_async
from punit import fact, trait
from typing import Any
from uuid import UUID, uuid4


def get_mongodb_connectionstring():
    import appsettings2
    from deev.common.connection_string import ConnectionString
    configuration = appsettings2.get_configuration()
    connection_str = configuration.connections.mongo_test
    return ConnectionString(connection_str)


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_create_and_read_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=True)

        uid = f'async-create-read-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='hello')
        pk = await adapter.create(entity1)
        assert pk is not None
        assert pk.get('id') == uid

        result = await adapter.read(id=uid)
        assert result is not None
        assert result.value == 'hello'


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_create_kwargs_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        key = uuid4().hex

        pk = await adapter.create(id=f'async-kwargs-test-{key}', value='from_kwargs')
        assert pk is not None
        assert pk.get('id') == f'async-kwargs-test-{key}'

        result = await adapter.read(id=f'async-kwargs-test-{key}')
        assert result is not None
        assert result.value == 'from_kwargs'


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_update_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'async-update-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='original')
        await adapter.create(entity1)

        entity1.value = 'async-updated'
        await adapter.update(entity1)

        result = await adapter.read(id=uid)
        assert result is not None
        assert result.value == 'async-updated'


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_delete_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'async-delete-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='gone')
        await adapter.create(entity1)

        await adapter.delete(id=uid)
        result = await adapter.read(id=uid)
        assert result is None


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_exists_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'async-exists-{uuid4().hex[:8]}'
        assert await adapter.exists(id=uid) is False

        entity1 = TestEntity(id=uid, value='exists')
        await adapter.create(entity1)

        assert await adapter.exists(id=uid) is True


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_upsert_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'async-upsert-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='new')
        pk = await adapter.upsert(entity1)
        assert pk.get('id') == uid

        entity1.value = 'async-updated-upsert'
        await adapter.upsert(entity1)
        result = await adapter.read(id=uid)
        assert result is not None
        assert result.value == 'async-updated-upsert'


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_query_returns_all() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        base_id = 'async-query-all-'
        inserted_ids = []
        for i in range(3):
            eid = f'{base_id}{uuid4().hex}'
            entity1 = TestEntity(id=eid, value=f'async_value_{i}')
            await adapter.create(entity1)
            inserted_ids.append(eid)

        results = []
        async for r in adapter.query():
            results.append(r)
        found_ids = {getattr(r, 'id', None) for r in results}
        for eid in inserted_ids:
            assert eid in found_ids, f'Expected entity {eid} not found in query results'


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_query_with_where_works() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)

        match_id = f'async-qwhere-match-{uuid4().hex}'
        no_match_id = f'async-qwhere-nomatch-{uuid4().hex}'
        entity1 = TestEntity(id=match_id, value='unique-async-match-xyz')
        entity2 = TestEntity(id=no_match_id, value='unique-async-nomatch-xyz')
        await adapter.create(entity1)
        await adapter.create(entity2)

        results = []
        async for r in adapter.query(where="value='unique-async-match-xyz'"):
            results.append(r)
        found_ids = {getattr(r, 'id', None) for r in results}
        assert match_id in found_ids
        assert no_match_id not in found_ids


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_primary_key_property() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[TestEntity](connection, create_table=False)
        assert adapter.primary_key == ('id',)


@fact
@trait('integration')
@trait('mongodb')
async def async_adapter_uuid_pk_roundtrip() -> None:
    conn_str = get_mongodb_connectionstring()
    async with await connect_async(conn_str) as connection:
        @entity
        class UuidPkEntity:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = AsyncMongoTableAdapter[UuidPkEntity](connection, create_table=False)

        uuid_val = uuid4()
        entity1 = UuidPkEntity(id=uuid_val, value='async-hello')
        pk = await adapter.create(entity1)
        assert pk is not None

        result = await adapter.read(id=uuid_val)
        assert result is not None
        assert result.value == 'async-hello'
