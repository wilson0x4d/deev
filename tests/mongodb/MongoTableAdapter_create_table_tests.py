# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field, IndexOptions, IndexOrder
from deev.mongodb.MongoTableAdapter import MongoTableAdapter
from punit import fact, trait
from unittest.mock import MagicMock
import pymongo


def _make_mock_connection():
    """Build mock chain for create_table testing.

    Returns: (connection, cursor, client, db, collection)
    All mocks pre-wired so that __deferred_init triggers index creation path.
    """
    mock_session = MagicMock()
    mock_client = MagicMock(spec=pymongo.MongoClient)

    mock_cursor = MagicMock()
    mock_cursor.mongo_session = mock_session

    mock_db = MagicMock()
    mock_db.list_collection_names.return_value = []  # type: ignore[misc]  # noqa: E501

    mock_collection = MagicMock(spec=pymongo.collection.Collection)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_db.create_collection = MagicMock(return_value=mock_collection)

    mock_client.get_database.return_value = mock_db

    mock_connection = MagicMock()
    mock_connection.mongo_client = mock_client
    mock_connection.mongo_database_name = 'test_db'
    mock_connection.cursor.return_value = mock_cursor

    return mock_connection, mock_cursor, mock_client, mock_db, mock_collection


@fact
@trait('unit', 'mongodb')
def pk_creates_unique_index() -> None:
    @entity
    class PKEntity:
        id: str = field(primary_key=True)
        name: str

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = MongoTableAdapter[PKEntity](mock_connection, create_table=True)
    # Trigger deferred init via a public method call (the one that actually hits the DB).
    # Since we're mocking everything below this point, it works without a real connection.
    adapter.read(id='x')  # noqa: E501

    assert mock_collection.create_index.call_count == 1

    call = mock_collection.create_index.call_args_list[0]
    keys_arg = call[0][0] if call[0] else call[1].get('keys')
    assert keys_arg == {'id': 1}
    assert call[1]['unique'] is True


@fact
@trait('unit', 'mongodb')
def single_field_secondary_index() -> None:
    @entity
    class SingleIndexEntity:
        id: str = field(primary_key=True)
        name: str = field(index='ix_single')

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = MongoTableAdapter[SingleIndexEntity](mock_connection, create_table=True)
    adapter.read(id='x')  # noqa: E501

    assert mock_collection.create_index.call_count == 2

    # PK index call (index 0)
    pk_call = mock_collection.create_index.call_args_list[0]
    pk_keys = pk_call[0][0] if pk_call[0] else pk_call[1].get('keys')
    assert pk_keys == {'id': 1}
    assert pk_call[1]['unique'] is True

    # Secondary index call (index 1)
    secondary = mock_collection.create_index.call_args_list[1]
    sec_keys = secondary[0][0] if secondary[0] else secondary[1].get('keys')
    assert sec_keys == [('name', 1)]
    assert secondary[1]['comment'] == 'ix_single'


@fact
@trait('unit', 'mongodb')
def compound_index_sorted() -> None:
    @entity
    class CompoundIndexEntity:
        id: str = field(primary_key=True)
        last_name: str = field(index='ix_user_composite')
        first_name: str = field(index='ix_user_composite')

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = MongoTableAdapter[CompoundIndexEntity](mock_connection, create_table=True)
    adapter.read(id='x')  # noqa: E501

    assert mock_collection.create_index.call_count == 2

    # Secondary index should be alphabetically sorted by field name
    secondary = mock_collection.create_index.call_args_list[1]
    sec_keys = secondary[0][0] if secondary[0] else secondary[1].get('keys')
    assert sec_keys == [('first_name', 1), ('last_name', 1)]
    assert secondary[1]['comment'] == 'ix_user_composite'


@fact
@trait('unit', 'mongodb')
def descending_secondary_index() -> None:
    @entity
    class DescIndexEntity:
        id: str = field(primary_key=True)
        updated_at: str = field(
            index=IndexOptions(name='ix_desc', direction=IndexOrder.DESCENDING, rank=0)
        )

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = MongoTableAdapter[DescIndexEntity](mock_connection, create_table=True)
    adapter.read(id='x')  # noqa: E501

    assert mock_collection.create_index.call_count == 2

    secondary = mock_collection.create_index.call_args_list[1]
    sec_keys = secondary[0][0] if secondary[0] else secondary[1].get('keys')
    assert sec_keys == [('updated_at', -1)]
    assert sec_keys[0][1] == pymongo.DESCENDING
    assert secondary[1]['comment'] == 'ix_desc'


@fact
@trait('unit', 'mongodb')
def mixed_direction_compound_index() -> None:
    @entity
    class MixedCompoundEntity:
        id: str = field(primary_key=True)
        first_name: str = field(
            index=IndexOptions(name='ix_mixed', direction=IndexOrder.ASCENDING, rank=0)
        )
        updated_at: str = field(
            index=IndexOptions(name='ix_mixed', direction=IndexOrder.DESCENDING, rank=0)
        )

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = MongoTableAdapter[MixedCompoundEntity](mock_connection, create_table=True)
    adapter.read(id='x')  # noqa: E501

    assert mock_collection.create_index.call_count == 2

    secondary = mock_collection.create_index.call_args_list[1]
    sec_keys = secondary[0][0] if secondary[0] else secondary[1].get('keys')
    assert len(sec_keys) == 2
    assert sec_keys[0] == ('first_name', pymongo.ASCENDING)
    assert sec_keys[1] == ('updated_at', pymongo.DESCENDING)
    assert secondary[1]['comment'] == 'ix_mixed'


@fact
@trait('unit', 'mongodb')
def no_secondary_indexes_only_pk() -> None:
    @entity
    class NoSecondaryEntity:
        id: str = field(primary_key=True)
        name: str
        value: int

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = MongoTableAdapter[NoSecondaryEntity](mock_connection, create_table=True)
    adapter.read(id='x')  # noqa: E501

    assert mock_collection.create_index.call_count == 1

    pk_call = mock_collection.create_index.call_args_list[0]
    pk_keys = pk_call[0][0] if pk_call[0] else pk_call[1].get('keys')
    assert pk_keys == {'id': 1}
    assert pk_call[1]['unique'] is True
