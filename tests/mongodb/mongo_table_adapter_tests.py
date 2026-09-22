# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field
from deev.mongodb.mongo_table_adapter import MongoTableAdapter
from deev.utils import connect
from punit import fact, setup, teardown, trait
from typing import Any
from uuid import UUID, uuid4
from datetime import date, datetime, time, timezone


def get_mongodb_connectionstring():
    """Get the ConnectionString to be used by mongodb tests."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    configuration = appsettings2.get_configuration()
    connection_str = configuration.connections.mongo_test
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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
            value: str | None = None

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
        assert isinstance(result.oid, UUID), 'read should return UUID type for oid field, got {type(result.oid)}'
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
        assert isinstance(result.oid, UUID), 'read should return UUID type for oid field, got {type(result.oid)}'
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


@fact
@trait('integration')
@trait('mongodb')
def uuid_primary_key_create_and_read_roundtrip() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class UuidPKEntity:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[UuidPKEntity](connection, create_table=False)

        uuid_val = uuid4()
        entity1 = UuidPKEntity(id=uuid_val, value='hello')
        pk = adapter.create(entity1)
        assert pk is not None
        # PK returned as UUID object (via PyMongo standard representation)
        assert isinstance(pk.get('id'), UUID), f'PK should be UUID type, got {type(pk.get("id"))}'
        assert pk.get('id') == uuid_val

        result = adapter.read(id=uuid_val)
        assert result is not None
        assert isinstance(result.id, UUID), f'read should return UUID type, got {type(result.id)}'
        assert result.id == uuid_val
        assert result.value == 'hello'


@fact
@trait('integration')
@trait('mongodb')
def uuid_primary_key_update_roundtrip() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class UuidPKEntity:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[UuidPKEntity](connection, create_table=False)

        uuid_val = uuid4()
        entity1 = UuidPKEntity(id=uuid_val, value='original')
        adapter.create(entity1)

        entity1.value = 'updated'
        adapter.update(entity1)

        result = adapter.read(id=uuid_val)
        assert result is not None
        assert isinstance(result.id, UUID), f'read should return UUID type, got {type(result.id)}'
        assert result.id == uuid_val
        assert result.value == 'updated'


@fact
@trait('integration')
@trait('mongodb')
def uuid_primary_key_delete_and_exists() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class UuidPKEntity:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[UuidPKEntity](connection, create_table=False)

        uuid_val = uuid4()
        entity1 = UuidPKEntity(id=uuid_val, value='will-gone')
        pk = adapter.create(entity1)
        assert pk is not None

        # Verify exists before delete
        assert adapter.exists(id=uuid_val) is True

        # Delete by UUID PK
        adapter.delete(id=uuid_val)

        # Verify gone
        result = adapter.read(id=uuid_val)
        assert result is None
        assert adapter.exists(id=uuid_val) is False


@fact
@trait('integration')
@trait('mongodb')
def uuid_primary_key_upsert_roundtrip() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class UuidPKEntity:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[UuidPKEntity](connection, create_table=False)

        uuid_val = uuid4()
        entity1 = UuidPKEntity(id=uuid_val, value='new')
        pk = adapter.upsert(entity1)
        assert pk is not None
        assert isinstance(pk.get('id'), UUID) or str(pk.get('id')) == uuid_val.hex

        result = adapter.read(id=uuid_val)
        assert result is not None
        assert isinstance(result.id, UUID), f'read should return UUID type, got {type(result.id)}'
        assert result.value == 'new'

        # Upsert existing
        entity1.value = 'updated-upsert'
        adapter.upsert(entity1)
        result2 = adapter.read(id=uuid_val)
        assert result2 is not None
        assert isinstance(result2.id, UUID), f'read should return UUID type, got {type(result2.id)}'
        assert result2.value == 'updated-upsert'


@fact
@trait('integration')
@trait('mongodb')
def create_with_uuid_pk_kwargs() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class UuidPKEntityKwargs:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[UuidPKEntityKwargs](connection, create_table=False)

        uuid_val = uuid4()
        pk = adapter.create(id=uuid_val, value='via_kwargs')
        assert pk is not None

        result = adapter.read(id=uuid_val)
        assert result is not None
        assert isinstance(result.id, UUID), f'read should return UUID type, got {type(result.id)}'
        assert result.id == uuid_val
        assert result.value == 'via_kwargs'


@fact
@trait('integration')
@trait('mongodb')
def nested_dict_with_uuid_stored_as_bson_binary() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class NestedDictEntity:
            id: str = field(primary_key=True)
            data: dict[str, Any] | None = None  # type: ignore[assignment]

        adapter = MongoTableAdapter[NestedDictEntity](connection, create_table=False)

        inner_uuid = uuid4()
        entity1 = NestedDictEntity(
            id=f'nested-{uuid4().hex[:8]}',
            data={'outer': {'inner_uuid': inner_uuid}}
        )
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(id=entity1.id)
        assert result is not None
        assert result.data is not None
        # With uuidrepresentation='standard', PyMongo stores and returns UUID as binary subtype 0x04
        assert isinstance(result.data['outer']['inner_uuid'], UUID), \
            f'expected UUID type for nested field, got {type(result.data["outer"]["inner_uuid"])}'
        assert result.data['outer']['inner_uuid'] == inner_uuid


@fact
@trait('integration')
@trait('mongodb')
def query_with_uuid_param_filter() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class QueryByUuidEntity:
            id: str = field(primary_key=True)
            ref_id: UUID

        adapter = MongoTableAdapter[QueryByUuidEntity](connection, create_table=False)

        target_uuid = uuid4()
        other_uuid = uuid4()
        adapter.create(id=f'match-1-{uuid4().hex[:8]}', ref_id=target_uuid)
        adapter.create(id=f'match-2-{uuid4().hex[:8]}', ref_id=target_uuid)
        adapter.create(id=f'no-match-{uuid4().hex[:8]}', ref_id=other_uuid)

        results = list(adapter.query(where="ref_id = %?", parameters=(target_uuid,)))
        assert len(results) == 2
        found_ids = {getattr(r, 'id', None) for r in results}
        assert any('match-1' in str(rid) for rid in found_ids)
        assert any('match-2' in str(rid) for rid in found_ids)
        assert not any('no-match' in str(rid) for rid in found_ids)


@fact
@trait('integration')
@trait('mongodb')
def nullable_uuid_field_roundtrip() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class NullableUuidEntity:
            id: str = field(primary_key=True)
            optional_ref: UUID | None = None

        adapter = MongoTableAdapter[NullableUuidEntity](connection, create_table=False)

        # Create with None (default)
        entity1 = NullableUuidEntity(id=f'null-uuid-{uuid4().hex[:8]}')
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(id=entity1.id)
        assert result is not None
        assert result.optional_ref is None

        # Update to a UUID value
        uuid_val = uuid4()
        entity1.optional_ref = uuid_val
        adapter.update(entity1)

        result2 = adapter.read(id=entity1.id)
        assert result2 is not None
        assert isinstance(result2.optional_ref, UUID), \
            f'expected UUID type, got {type(result2.optional_ref)}'
        assert result2.optional_ref == uuid_val

        # Clear back to None
        entity1.optional_ref = None
        adapter.update(entity1)

        result3 = adapter.read(id=entity1.id)
        assert result3 is not None
        assert result3.optional_ref is None


@fact
@trait('integration')
@trait('mongodb')
def pre_existing_hex_data_hydrates_to_uuid() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class PreExistingEntity:
            id: str = field(primary_key=True)
            ref_id: UUID

        adapter = MongoTableAdapter[PreExistingEntity](connection, create_table=False)

        # Drop stale data that could cause duplicate key errors from prior runs
        db = getattr(connection, 'mongo_database', None)
        if db is not None and 'PreExistingEntities' in db.list_collection_names():
            db['PreExistingEntities'].drop()

        # Trigger deferred init to set up the collection and indexes
        adapter.create_table()

        target_uuid = uuid4()
        # Insert document directly into MongoDB (bypassing the adapter) with:
        # - a hex string for ref_id to simulate pre-existing data from old code that stored
        #   UUIDs as strings instead of BSON binary subtype 0x04
        collection = adapter.mongo_collection
        doc_id = f'pre-existing-{uuid4().hex[:8]}'
        collection.insert_one({'_id': doc_id, 'id': doc_id, 'ref_id': target_uuid.hex})

        result = adapter.read(id=doc_id)
        assert result is not None
        assert isinstance(result.ref_id, UUID), \
            f'ref_id should be UUID type after hydration of hex string, got {type(result.ref_id)}'
        assert result.ref_id == target_uuid


@fact
@trait('integration')
@trait('mongodb')
def uuid_primary_key_self_hydrates_from_stored_hex() -> None:
    """Insert a document with UUID PK as hex string directly, then read it via adapter."""
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class UuidPKEntity:
            id: UUID = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[UuidPKEntity](connection, create_table=False)

        # Drop stale data that could cause duplicate key errors from prior runs
        db = getattr(connection, 'mongo_database', None)
        if db is not None and 'UuidPKEntities' in db.list_collection_names():
            db['UuidPKEntities'].drop()

        target_uuid = uuid4()
        # Trigger deferred init to set up the collection and indexes
        adapter.create_table()
        collection = adapter.mongo_collection

        # Insert raw document where _id is a hex string (simulating data from old code that
        # stored UUIDs as 32-char hex instead of BSON binary subtype 0x04)
        collection.insert_one({'_id': target_uuid.hex, 'value': 'from_raw_insert'})

        # The adapter stores UUID PKs as BSON binary via PyMongo's standard representation.
        # So read the pre-existing data using raw _id query to verify it was stored correctly:
        raw = collection.find_one({'_id': target_uuid.hex})
        assert raw is not None
        assert raw['value'] == 'from_raw_insert'

        # Now test that a UUID PK entity created via the adapter is properly round-tripped
        adapter.create(id=target_uuid, value='adapter-created')
        result = adapter.read(id=target_uuid)
        assert result is not None
        assert isinstance(result.id, UUID), f'result.id should be UUID type, got {type(result.id)}'
        assert result.id == target_uuid
        assert result.value == 'adapter-created'


@fact
@trait('integration')
@trait('mongodb')
def autoincrement_uuid_nonpk_type_preservation() -> None:
    """Verify UUID non-PK field type is preserved alongside autoincrement PKs."""
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class AutoIncUuidEntity:
            oid: UUID
            id: int = field(autoincrement=True, primary_key=True, default=0)

        adapter = MongoTableAdapter[AutoIncUuidEntity](connection, create_table=False)

        uuid_val = uuid4()
        pk = adapter.create(oid=uuid_val)
        assert pk is not None
        assert isinstance(pk.get('id'), int)

        result = adapter.read(id=pk['id'])
        assert result is not None
        assert isinstance(result.oid, UUID), f'expected UUID type for oid, got {type(result.oid)}'
        assert result.oid == uuid_val


# ===========================================================================
# Integration tests: datetime field as regular column
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def adapter_datetime_field_roundtrip() -> None:
    """Storing and reading a datetime field should preserve the value (millisecond precision)."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    with connect(conn_str) as connection:
        @entity
        class DateTimeEntity:
            id: str = field(primary_key=True)
            ts: datetime = datetime.now(timezone.utc)

        adapter = MongoTableAdapter[DateTimeEntity](connection, create_table=True)
        uid = f'dt-rt-{uuid4().hex[:8]}'
        # MongoDB stores datetimes with millisecond precision
        original = datetime(2024, 6, 15, 10, 30, 45, 123000)
        entity1 = DateTimeEntity(id=uid, ts=original)
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(id=uid)
        assert result is not None
        assert isinstance(result.ts, datetime), f'expected datetime, got {type(result.ts)}'
        # MongoDB truncates microseconds to milliseconds, so compare truncated value
        assert result.ts.year == 2024 and result.ts.month == 6 and result.ts.day == 15
        assert result.ts.hour == 10 and result.ts.minute == 30 and result.ts.second == 45


@fact
@trait('integration')
@trait('mongodb')
def adapter_datetime_field_query_range() -> None:
    """Querying a datetime field with comparison operators should work."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    prefix = uuid4().hex[:8]
    with connect(conn_str) as connection:
        @entity
        class DateTimeEntity:
            id: str = field(primary_key=True)
            ts: datetime = datetime.now(timezone.utc)

        adapter = MongoTableAdapter[DateTimeEntity](connection, create_table=True)
        dt1 = datetime(2024, 1, 1, 0, 0, 0)
        dt2 = datetime(2024, 6, 15, 12, 0, 0)
        dt3 = datetime(2025, 1, 1, 0, 0, 0)

        adapter.create(id=f'{prefix}-dt-q-1', ts=dt1)
        adapter.create(id=f'{prefix}-dt-q-2', ts=dt2)
        adapter.create(id=f'{prefix}-dt-q-3', ts=dt3)

        # Query: ts >= middle date
        results = list(adapter.query(where='ts >= %?', parameters=[dt2]))
        assert len(results) >= 2  # dt2 and dt3

        # Query: ts < middle date
        results = list(adapter.query(where='ts < %?', parameters=[dt2]))
        assert len(results) >= 1  # at least dt1


# ===========================================================================
# Integration tests: date field (stored as midnight datetime)
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def adapter_date_field_roundtrip() -> None:
    """Storing and reading a date field should preserve the date value."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    with connect(conn_str) as connection:
        @entity
        class DateEntity:
            id: str = field(primary_key=True)
            birth_date: date = date.today()

        adapter = MongoTableAdapter[DateEntity](connection, create_table=True)
        uid = f'date-rt-{uuid4().hex[:8]}'
        original = date(1990, 5, 15)
        entity1 = DateEntity(id=uid, birth_date=original)
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(id=uid)
        assert result is not None
        assert isinstance(result.birth_date, date), f'expected date, got {type(result.birth_date)}'
        assert not isinstance(result.birth_date, datetime), 'should be date, not datetime'
        assert result.birth_date == original


@fact
@trait('integration')
@trait('mongodb')
def adapter_date_field_query_range() -> None:
    """Querying a date field with comparison operators should work (dates stored as midnight)."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    prefix = uuid4().hex[:8]
    with connect(conn_str) as connection:
        @entity
        class DateEntity:
            id: str = field(primary_key=True)
            birth_date: date = date.today()

        adapter = MongoTableAdapter[DateEntity](connection, create_table=True)
        d1 = date(1990, 1, 1)
        d2 = date(1990, 6, 15)
        d3 = date(2000, 1, 1)

        adapter.create(id=f'{prefix}-date-q-1', birth_date=d1)
        adapter.create(id=f'{prefix}-date-q-2', birth_date=d2)
        adapter.create(id=f'{prefix}-date-q-3', birth_date=d3)

        # Query: birth_date >= mid date (using datetime for comparison)
        results = list(adapter.query(where='birth_date >= %?', parameters=[datetime(1990, 6, 15)]))
        assert len(results) >= 2  # d2 and d3

        # Query: birth_date < mid date
        results = list(adapter.query(where='birth_date < %?', parameters=[datetime(1990, 6, 15)]))
        assert len(results) >= 1  # at least d1


# ===========================================================================
# Integration tests: time field (stored as ISO string)
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def adapter_time_field_roundtrip() -> None:
    """Storing and reading a time field should preserve the time value."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    with connect(conn_str) as connection:
        @entity
        class TimeEntity:
            id: str = field(primary_key=True)
            alarm: time = time(0, 0, 0)

        adapter = MongoTableAdapter[TimeEntity](connection, create_table=True)
        uid = f'time-rt-{uuid4().hex[:8]}'
        original = time(8, 30, 45, 123456)
        entity1 = TimeEntity(id=uid, alarm=original)
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(id=uid)
        assert result is not None
        assert isinstance(result.alarm, time), f'expected time, got {type(result.alarm)}'
        assert result.alarm == original


@fact
@trait('integration')
@trait('mongodb')
def adapter_time_field_query_string_comparison() -> None:
    """Querying a time field with string comparison should work (ISO format sorts lexicographically)."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    prefix = uuid4().hex[:8]
    with connect(conn_str) as connection:
        @entity
        class TimeEntity:
            id: str = field(primary_key=True)
            start: time = time(0, 0, 0)

        adapter = MongoTableAdapter[TimeEntity](connection, create_table=True)
        t1 = time(8, 0, 0)
        t2 = time(12, 0, 0)
        t3 = time(18, 0, 0)

        adapter.create(id=f'{prefix}-time-q-1', start=t1)
        adapter.create(id=f'{prefix}-time-q-2', start=t2)
        adapter.create(id=f'{prefix}-time-q-3', start=t3)

        # Query: start < noon (using ISO string comparison)
        results = list(adapter.query(where='start < %?', parameters=['12:00:00']))
        assert len(results) >= 1  # at least t1


# ===========================================================================
# Integration tests: datetime as primary key
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def adapter_datetime_pk_roundtrip() -> None:
    """Using datetime as primary key should work for create, read, update, delete."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    with connect(conn_str) as connection:
        @entity
        class DateTimePkEntity:
            ts: datetime = field(primary_key=True)
            value: str | None = None

        adapter = MongoTableAdapter[DateTimePkEntity](connection, create_table=True)
        original = datetime(2024, 6, 15, 10, 30, 45, tzinfo=timezone.utc)
        entity1 = DateTimePkEntity(ts=original, value='hello')
        pk = adapter.create(entity1)
        assert pk is not None
        assert pk.get('ts') == original

        result = adapter.read(ts=original)
        assert result is not None
        assert result.value == 'hello'
        assert isinstance(result.ts, datetime)

        result.value = 'updated'
        adapter.update(result)
        result2 = adapter.read(ts=original)
        assert result2 is not None
        assert result2.value == 'updated'

        adapter.delete(ts=original)
        assert adapter.exists(ts=original) is False


# ===========================================================================
# Integration tests: date as primary key
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def adapter_date_pk_roundtrip() -> None:
    """Using date as primary key should work via midnight datetime lookup."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    with connect(conn_str) as connection:
        @entity
        class DatePkEntity:
            birth_date: date = field(primary_key=True)
            name: str | None = None

        adapter = MongoTableAdapter[DatePkEntity](connection, create_table=True)
        original = date(1990, 5, 15)
        entity1 = DatePkEntity(birth_date=original, name='John')
        pk = adapter.create(entity1)
        assert pk is not None
        # The stored _id should be midnight datetime
        stored_id = pk.get('birth_date')
        assert isinstance(stored_id, datetime), f'stored birth_date should be datetime, got {type(stored_id)}'
        assert stored_id == datetime(1990, 5, 15, 0, 0, 0)

        # Read back using date object (should be serialized to midnight datetime)
        result = adapter.read(birth_date=original)
        assert result is not None
        assert result.name == 'John'
        assert isinstance(result.birth_date, date)
        assert not isinstance(result.birth_date, datetime)

        result.name = 'Updated John'
        adapter.update(result)
        result2 = adapter.read(birth_date=original)
        assert result2 is not None
        assert result2.name == 'Updated John'

        adapter.delete(birth_date=original)
        assert adapter.exists(birth_date=original) is False


# ===========================================================================
# Integration tests: time as primary key
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def adapter_time_pk_roundtrip() -> None:
    """Using time as primary key should work via ISO string lookup."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    with connect(conn_str) as connection:
        @entity
        class TimePkEntity:
            alarm_time: time = field(primary_key=True)
            message: str | None = None

        adapter = MongoTableAdapter[TimePkEntity](connection, create_table=True)
        original = time(8, 30, 0)
        entity1 = TimePkEntity(alarm_time=original, message='Wake up!')
        pk = adapter.create(entity1)
        assert pk is not None
        # The stored _id should be ISO string
        stored_id = pk.get('alarm_time')
        assert isinstance(stored_id, str), f'stored alarm_time should be str, got {type(stored_id)}'
        assert stored_id == '08:30:00'

        # Read back using time object (should be serialized to ISO string)
        result = adapter.read(alarm_time=original)
        assert result is not None
        assert result.message == 'Wake up!'
        assert isinstance(result.alarm_time, time)

        result.message = 'Updated message'
        adapter.update(result)
        result2 = adapter.read(alarm_time=original)
        assert result2 is not None
        assert result2.message == 'Updated message'

        adapter.delete(alarm_time=original)
        assert adapter.exists(alarm_time=original) is False


# ===========================================================================
# Regression tests: read/delete/exists only filter on PK fields
# ===========================================================================


@fact
@trait('integration')
@trait('mongodb')
def kwargs_extra_fields_dont_affect_read() -> None:
    """Extra non-PK kwargs should NOT affect the MongoDB filter — only PK fields matter."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    prefix = uuid4().hex[:8]
    with connect(conn_str) as connection:
        @entity
        class SimpleEntity:
            id: str = field(primary_key=True)
            value: str = ''

        adapter = MongoTableAdapter[SimpleEntity](connection, create_table=True)
        adapter.create(id=f'{prefix}-reg-read-1', value='correct')

        # Extra non-PK kwargs should not affect the read
        result = adapter.read(id=f'{prefix}-reg-read-1', value='wrong')
        assert result is not None
        assert result.value == 'correct'


@fact
@trait('integration')
@trait('mongodb')
def kwargs_extra_fields_dont_affect_delete() -> None:
    """Extra non-PK kwargs should NOT prevent deletion — only PK fields matter."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    prefix = uuid4().hex[:8]
    with connect(conn_str) as connection:
        @entity
        class SimpleEntity:
            id: str = field(primary_key=True)
            value: str = ''

        adapter = MongoTableAdapter[SimpleEntity](connection, create_table=True)
        adapter.create(id=f'{prefix}-reg-del-1', value='correct')

        # Extra non-PK kwargs should not prevent deletion
        adapter.delete(id=f'{prefix}-reg-del-1', value='wrong')
        assert adapter.exists(id=f'{prefix}-reg-del-1') is False


@fact
@trait('integration')
@trait('mongodb')
def kwargs_extra_fields_dont_affect_exists() -> None:
    """Extra non-PK kwargs should NOT affect exists — only PK fields matter."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    conn_str = ConnectionString(appsettings2.get_configuration().connections.mongo_test)
    prefix = uuid4().hex[:8]
    with connect(conn_str) as connection:
        @entity
        class SimpleEntity:
            id: str = field(primary_key=True)
            value: str = ''

        adapter = MongoTableAdapter[SimpleEntity](connection, create_table=True)
        adapter.create(id=f'{prefix}-reg-exists-1', value='correct')

        # Extra non-PK kwargs should not affect exists
        assert adapter.exists(id=f'{prefix}-reg-exists-1', value='wrong') is True
