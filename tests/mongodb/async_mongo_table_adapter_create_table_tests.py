# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field, IndexOptions
from deev.mongodb.async_mongo_table_adapter import AsyncMongoTableAdapter
from punit import fact, trait
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from unittest.mock import AsyncMock, MagicMock


def _make_mock_connection():
    """Build mock chain for create_table testing.

    Returns: (connection, cursor, client, db, collection)
    All mocks pre-wired so that create_table() exercises index creation.
    """
    mock_session = MagicMock()
    mock_client = MagicMock(spec=AsyncMongoClient)

    mock_cursor = MagicMock()
    mock_cursor.mongo_session = mock_session

    mock_db = MagicMock()
    mock_db.list_collection_names = AsyncMock(return_value=[])

    mock_collection = MagicMock(spec=AsyncCollection)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_db.create_collection = AsyncMock(return_value=mock_collection)

    mock_client.get_database.return_value = mock_db

    mock_connection = MagicMock()
    mock_connection.mongo_client = mock_client
    mock_connection.mongo_database_name = 'test_db'
    mock_connection.cursor = AsyncMock(return_value=mock_cursor)

    return mock_connection, mock_cursor, mock_client, mock_db, mock_collection


@fact
@trait('unit', 'mongodb')
async def async_compound_index_rank_ordered() -> None:
    @entity
    class AsyncRankOrderedEntity:
        id: str = field(primary_key=True)
        zeta: str = field(index=IndexOptions(name='ix_asyrrank', rank=0))
        alpha: str = field(index=IndexOptions(name='ix_asyrrank', rank=1))

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = AsyncMongoTableAdapter[AsyncRankOrderedEntity](mock_connection, create_table=False)
    await adapter.create_table()

    assert mock_collection.create_index.call_count == 2, f'(expected=2, actual={mock_collection.create_index.call_count})'

    secondary = mock_collection.create_index.call_args_list[1]
    sec_keys = secondary[0][0] if secondary[0] else secondary[1].get('keys')
    assert sec_keys == [('zeta', 1), ('alpha', 1)], f'(expected=[("zeta", 1), ("alpha", 1)], actual={sec_keys})'
    assert secondary[1]['comment'] == 'ix_asyrrank', f"(expected='ix_asyrrank', actual={secondary[1].get('comment')})"


@fact
@trait('unit', 'mongodb')
async def async_single_field_in_multiple_indexes() -> None:
    @entity
    class AsyncMultiIndexEntity:
        id: str = field(primary_key=True)
        status: str = field(index=[IndexOptions(name='ix_asyrstatus', rank=0), IndexOptions(name='ix_asyrstatus_priority', rank=1)])
        priority: int = field(index=IndexOptions(name='ix_asyrstatus_priority', rank=2))

    mock_connection, _, _, _, mock_collection = _make_mock_connection()
    adapter = AsyncMongoTableAdapter[AsyncMultiIndexEntity](mock_connection, create_table=False)
    await adapter.create_table()

    assert mock_collection.create_index.call_count == 3, f'(expected=3, actual={mock_collection.create_index.call_count})'

    calls = {c[1]['comment']: c[1] for c in mock_collection.create_index.call_args_list if 'comment' in c[1]}
    assert calls['ix_asyrstatus']['keys'] == [('status', 1)], f'unexpected keys: {calls["ix_asyrstatus"]["keys"]}'
    assert calls['ix_asyrstatus_priority']['keys'] == [('status', 1), ('priority', 1)], f'unexpected keys: {calls["ix_asyrstatus_priority"]["keys"]}'
