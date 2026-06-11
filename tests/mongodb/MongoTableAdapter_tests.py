# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field
from deev.mongodb.MongoTableAdapter import MongoTableAdapter
from deev.utils import connect
from punit import fact, trait
from typing import Optional
from uuid import uuid4


def get_mongodb_connectionstring():
    """Get the ConnectionString to be used by mongodb tests."""
    import appsettings2
    from deev.common.ConnectionString import ConnectionString
    configuration = appsettings2.get_configuration()
    connection_str = configuration.connections.mongodb_test
    return ConnectionString(connection_str)


@fact
@trait('integration')
@trait('mongodb')
def adapter_create_and_read_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=True)

        uid = f'create-read-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='hello')
        pk = adapter.create(entity1)
        assert pk is not None
        assert pk.get('id') == uid

        result = adapter.read(id=uid)
        assert result is not None
        assert result.value == 'hello'


@fact
@trait('integration')
@trait('mongodb')
def adapter_create_kwargs_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        key = uuid4().hex

        pk = adapter.create(id=f'kwargs-test-{key}', value='from_kwargs')
        assert pk is not None
        assert pk.get('id') == f'kwargs-test-{key}'

        result = adapter.read(id=f'kwargs-test-{key}')
        assert result is not None
        assert result.value == 'from_kwargs'


@fact
@trait('integration')
@trait('mongodb')
def adapter_update_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'update-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='original')
        adapter.create(entity1)

        entity1.value = 'updated'
        adapter.update(entity1)

        result = adapter.read(id=uid)
        assert result is not None
        assert result.value == 'updated'


@fact
@trait('integration')
@trait('mongodb')
def adapter_delete_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'delete-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='gone')
        adapter.create(entity1)

        adapter.delete(id=uid)
        result = adapter.read(id=uid)
        assert result is None


@fact
@trait('integration')
@trait('mongodb')
def adapter_exists_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'exists-{uuid4().hex[:8]}'
        assert adapter.exists(id=uid) is False

        entity1 = TestEntity(id=uid, value='exists')
        adapter.create(entity1)

        assert adapter.exists(id=uid) is True


@fact
@trait('integration')
@trait('mongodb')
def adapter_upsert_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'upsert-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='new')
        pk = adapter.upsert(entity1)
        assert pk.get('id') == uid

        # Upsert existing
        entity1.value = 'updated-upsert'
        adapter.upsert(entity1)
        result = adapter.read(id=uid)
        assert result is not None
        assert result.value == 'updated-upsert'


@fact
@trait('integration')
@trait('mongodb')
def adapter_upsert_inserts_if_not_exists() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'upsert-new-{uuid4().hex[:8]}'
        entity1 = TestEntity(id=uid, value='brand-new')
        pk = adapter.upsert(entity1)
        assert pk.get('id') == uid

        result = adapter.read(id=uid)
        assert result is not None
        assert result.value == 'brand-new'


@fact
@trait('integration')
@trait('mongodb')
def adapter_query_returns_all() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        # Insert multiple entities with unique IDs
        base_id = 'query-all-'
        inserted_ids = []
        for i in range(3):
            eid = f'{base_id}{uuid4().hex}'
            entity1 = TestEntity(id=eid, value=f'value_{i}')
            adapter.create(entity1)
            inserted_ids.append(eid)

        results = list(adapter.query())
        # Filter results to only those we just inserted (ignoring stale data from other tests)
        found_ids = {getattr(r, 'id', None) for r in results}
        for eid in inserted_ids:
            assert eid in found_ids, f'Expected entity {eid} not found in query results'


@fact
@trait('integration')
@trait('mongodb')
def adapter_query_with_where_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        match_id = f'qwhere-match-{uuid4().hex}'
        no_match_id = f'qwhere-nomatch-{uuid4().hex}'
        entity1 = TestEntity(id=match_id, value='unique-match-xyz')
        entity2 = TestEntity(id=no_match_id, value='unique-nomatch-xyz')
        adapter.create(entity1)
        adapter.create(entity2)

        results = list(adapter.query(where="value='unique-match-xyz'"))
        found_ids = {getattr(r, 'id', None) for r in results}
        assert match_id in found_ids
        assert no_match_id not in found_ids



@fact
@trait('integration')
@trait('mongodb')
def transaction_mongo_database_property_exists() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: Optional[str] = None

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)
        adapter.create_table()

        mongo_collection = getattr(adapter, 'mongo_collection', None)
        assert mongo_collection is not None, 'mongo_collection property should exist'
