# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field
from deev.mongodb.MongoTableAdapter import MongoTableAdapter
from deev.utils import connect
from punit import fact, setup, teardown, trait
from typing import Optional
from uuid import UUID, uuid4


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


@setup
def _drop_autoinc_collection() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        db = getattr(connection, 'mongo_database', None)
        if db is not None and 'AutoIncTestEntities' in db.list_collection_names():
            db['AutoIncTestEntities'].drop()


@fact
@trait('integration')
@trait('mongodb')
def adapter_create_with_autoincrement_returns_valid_id() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class AutoIncTestEntity:
            oid: UUID
            id: int = field(autoincrement=True, primary_key=True, default=0)

        adapter = MongoTableAdapter[AutoIncTestEntity](connection, create_table=True)

        pk1 = adapter.create(oid=uuid4())
        assert pk1 is not None
        assert isinstance(pk1.get('id'), int), 'autoincrement id should be an int'
        first_id = pk1['id']
        assert first_id >= 1, 'first autoincrement value should be >= 1'

        # Verify a second create also gets a valid id (monotonicity checked separately)
        oid2 = uuid4()
        adapter2 = MongoTableAdapter[AutoIncTestEntity](connection, create_table=False)
        pk2 = adapter2.create(oid=oid2)
        assert pk2 is not None
        assert isinstance(pk2.get('id'), int)
        # Confirm the value is actually persisted by reading it back
        result = adapter.read(id=pk2['id'])
        assert result is not None
        assert result.oid == oid2, 'persisted oid should match inserted oid'


@fact
@trait('integration')
@trait('mongodb')
def adapter_upsert_with_autoincrement_returns_valid_id() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class AutoIncTestEntity:
            oid: UUID
            id: int = field(autoincrement=True, primary_key=True, default=0)

        oid1 = uuid4()
        adapter = MongoTableAdapter[AutoIncTestEntity](connection, create_table=False)

        entity1 = AutoIncTestEntity(oid=oid1)
        pk1 = adapter.upsert(entity1)
        assert pk1 is not None
        assert isinstance(pk1.get('id'), int), 'autoincrement id should be an int'
        first_id = pk1['id']
        assert first_id >= 1, 'first autoincrement value should be >= 1'

        # Verify a second upsert also gets a valid id and persists correctly
        oid2 = uuid4()
        adapter2 = MongoTableAdapter[AutoIncTestEntity](connection, create_table=False)
        entity2 = AutoIncTestEntity(oid=oid2)
        pk2 = adapter2.upsert(entity2)
        assert pk2 is not None
        assert isinstance(pk2.get('id'), int)
        # Confirm the value is actually persisted by reading it back
        result = adapter.read(id=pk2['id'])
        assert result is not None
        assert result.oid == oid2, 'persisted oid should match upserted oid'


@fact
@trait('integration')
@trait('mongodb')
def create_autoincrement_returns_monotonically_increasing_ids() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class AutoIncTestEntity:
            oid: UUID
            id: int = field(autoincrement=True, primary_key=True, default=0)

        adapter = MongoTableAdapter[AutoIncTestEntity](connection, create_table=True)

        ids = []
        for _ in range(3):
            pk = adapter.create(oid=uuid4())
            assert pk is not None
            assert isinstance(pk.get('id'), int)
            ids.append(pk['id'])

        # Each subsequent id must be strictly greater than the previous
        assert ids[0] < ids[1], f'ids should be increasing but got {ids}'
        assert ids[1] < ids[2], f'ids should be increasing but got {ids}'


@fact
@trait('integration')
@trait('mongodb')
def upsert_autoincrement_returns_monotonically_increasing_ids() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class AutoIncTestEntity:
            oid: UUID
            id: int = field(autoincrement=True, primary_key=True, default=0)

        adapter = MongoTableAdapter[AutoIncTestEntity](connection, create_table=False)

        ids = []
        for _ in range(3):
            entity1 = AutoIncTestEntity(oid=uuid4())
            pk = adapter.upsert(entity1)
            assert pk is not None
            assert isinstance(pk.get('id'), int)
            ids.append(pk['id'])

        # Each subsequent id must be strictly greater than the previous
        assert ids[0] < ids[1], f'ids should be increasing but got {ids}'
        assert ids[1] < ids[2], f'ids should be increasing but got {ids}'
