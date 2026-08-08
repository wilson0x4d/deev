# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field, IndexOptions, IndexOrder
from deev.mysql.mysql_proxy_connection import MysqlProxyConnection
from deev.mysql.mysql_table_adapter import MysqlTableAdapter
from punit import fact, trait
from unittest.mock import MagicMock


def _make_mock_connection():
    """Build mock chain for index-creation testing.

    Uses spec=MysqlProxyConnection so the adapter's isinstance check passes
    and our mock is used directly (same pattern as MongoDB tests).

    Returns: (mock_connection, captured_sql_list)
    The captured list will contain all SQL strings executed via cursor.execute().
    """
    captured = []

    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = lambda sql, params=None: captured.append(sql)
    # description must be truthy for read()/query paths to work
    mock_cursor.description = [('id',), ('name',)]

    mock_connection = MagicMock(spec=MysqlProxyConnection)
    mock_connection.cursor.return_value = mock_cursor
    # commit/rollback are no-ops on the context level (proxy forwards them)
    mock_connection.commit.side_effect = lambda: None
    mock_connection.rollback.side_effect = lambda: None

    return mock_connection, captured


@fact
@trait('unit', 'mysql')
def single_column_pk_no_duplicate_index() -> None:
    @entity
    class SinglePkEntity:
        id: int = field(primary_key=True, autoincrement=True)
        name: str

    mock_connection, captured = _make_mock_connection()
    adapter = MysqlTableAdapter[SinglePkEntity](mock_connection, create_table=True)
    # Trigger deferred init via a public method call
    adapter.read(id=1)

    # First statement is CREATE TABLE (the second is SELECT from read())
    assert len(captured) >= 1
    assert 'CREATE TABLE' in captured[0]
    # No CREATE INDEX should appear anywhere
    assert not any('CREATE INDEX' in s for s in captured)


@fact
@trait('unit', 'mysql')
def single_secondary_index_string_shorthand() -> None:
    @entity
    class SingleIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        name: str = field(index='ix_single')

    mock_connection, captured = _make_mock_connection()
    adapter = MysqlTableAdapter[SingleIndexEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    # First is CREATE TABLE, second is CREATE INDEX (third is SELECT from read())
    assert len(captured) >= 2
    assert 'CREATE TABLE' in captured[0]

    # Verify secondary index
    index_sql = captured[1]
    assert 'CREATE INDEX' in index_sql
    assert 'ix_single' in index_sql
    assert '`name` ASC' in index_sql


@fact
@trait('unit', 'mysql')
def compound_secondary_index() -> None:
    @entity
    class CompoundIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        last_name: str = field(index='ix_user_composite')
        first_name: str = field(index='ix_user_composite')

    mock_connection, captured = _make_mock_connection()
    adapter = MysqlTableAdapter[CompoundIndexEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    # First is CREATE TABLE, second is CREATE INDEX (third is SELECT from read())
    assert len(captured) >= 2

    index_sql = captured[1]
    assert 'CREATE INDEX' in index_sql
    assert 'ix_user_composite' in index_sql
    # Fields should be sorted alphabetically: first_name before last_name
    first_pos = index_sql.index('first_name')
    last_pos = index_sql.index('last_name')
    assert first_pos < last_pos, 'Fields should be alphabetically sorted'
    assert '`first_name` ASC' in index_sql
    assert '`last_name` ASC' in index_sql


@fact
@trait('unit', 'mysql')
def descending_secondary_index() -> None:
    @entity
    class DescIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        updated_at: str = field(
            index=IndexOptions(name='ix_desc', direction=IndexOrder.DESCENDING)
        )

    mock_connection, captured = _make_mock_connection()
    adapter = MysqlTableAdapter[DescIndexEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    index_sql = captured[1]
    assert 'CREATE INDEX' in index_sql
    assert 'ix_desc' in index_sql
    assert '`updated_at` DESC' in index_sql


@fact
@trait('unit', 'mysql')
def mixed_direction_compound_index() -> None:
    @entity
    class MixedCompoundEntity:
        id: int = field(primary_key=True, autoincrement=True)
        first_name: str = field(
            index=IndexOptions(name='ix_mixed', direction=IndexOrder.ASCENDING)
        )
        updated_at: str = field(
            index=IndexOptions(name='ix_mixed', direction=IndexOrder.DESCENDING)
        )

    mock_connection, captured = _make_mock_connection()
    adapter = MysqlTableAdapter[MixedCompoundEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    index_sql = captured[1]
    assert 'CREATE INDEX' in index_sql
    assert 'ix_mixed' in index_sql
    assert '`first_name` ASC' in index_sql
    assert '`updated_at` DESC' in index_sql
    # Verify first_name comes before updated_at (alphabetically sorted)
    first_pos = index_sql.index('first_name')
    updated_pos = index_sql.index('updated_at')
    assert first_pos < updated_pos, 'Fields should be alphabetically sorted'


@fact
@trait('unit', 'mysql')
def no_secondary_indexes_only_create_table() -> None:
    @entity
    class NoSecondaryEntity:
        id: int = field(primary_key=True, autoincrement=True)
        name: str
        value: int

    mock_connection, captured = _make_mock_connection()
    adapter = MysqlTableAdapter[NoSecondaryEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    assert len(captured) >= 1
    assert 'CREATE TABLE' in captured[0]
    # No CREATE INDEX should appear anywhere
    assert not any('CREATE INDEX' in s for s in captured)
