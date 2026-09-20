# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import entity, field, IndexOptions, IndexOrder
from deev.mssql.mssql_proxy_connection import MSSQLProxyConnection
from deev.mssql.mssql_table_adapter import MSSQLTableAdapter
from punit import fact, trait
from unittest.mock import MagicMock


def _make_mock_connection():
    """Build mock chain for index-creation testing.

    Uses spec=MSSQLProxyConnection so the adapter's isinstance check passes
    and our mock is used directly (same pattern as MongoDB tests).

    Returns: (mock_connection, captured_sql_list)
    The captured list will contain all SQL strings executed via cursor.execute().
    """
    captured = []
    call_count = [0]

    def mock_execute(sql, params=None):
        captured.append(sql)
        call_count[0] += 1
        if call_count[0] == 1:
            # First execute is SELECT COUNT(*) FROM sys.tables ...
            # Return (0,) to indicate table doesn't exist → triggers DDL
            mock_cursor._fetch_result = (0,)
        else:
            mock_cursor._fetch_result = None

    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = mock_execute
    mock_cursor.fetchone.side_effect = lambda: getattr(mock_cursor, '_fetch_result', None)
    # description must be truthy for read()/query paths to work
    mock_cursor.description = [('id',), ('name',)]

    mock_connection = MagicMock(spec=MSSQLProxyConnection)
    mock_connection.cursor.return_value = mock_cursor
    # commit/rollback are no-ops on the context level (proxy forwards them)
    mock_connection.commit.side_effect = lambda: None
    mock_connection.rollback.side_effect = lambda: None

    return mock_connection, captured


@fact
@trait('unit', 'mssql')
def single_column_pk_no_duplicate_index() -> None:
    @entity
    class SinglePkEntity:
        id: int = field(primary_key=True, autoincrement=True)
        name: str

    mock_connection, captured = _make_mock_connection()
    adapter = MSSQLTableAdapter[SinglePkEntity](mock_connection, create_table=True)
    # Trigger deferred init via a public method call
    adapter.read(id=1)

    # First execute is SELECT COUNT(*) FROM sys.tables, second is CREATE TABLE, third is SELECT from read()
    assert len(captured) >= 2
    create_table_idx = next(i for i, s in enumerate(captured) if 'CREATE TABLE' in s)
    # No CREATE INDEX should appear anywhere
    assert not any('CREATE INDEX' in s for s in captured)


@fact
@trait('unit', 'mssql')
def single_secondary_index_string_shorthand() -> None:
    @entity
    class SingleIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        name: str = field(index='ix_single')

    mock_connection, captured = _make_mock_connection()
    adapter = MSSQLTableAdapter[SingleIndexEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    # First is SELECT COUNT(*) FROM sys.tables, second is CREATE TABLE, third is CREATE INDEX, fourth is SELECT from read()
    assert len(captured) >= 3
    create_table_idx = next(i for i, s in enumerate(captured) if 'CREATE TABLE' in s)
    create_index_idx = next(i for i, s in enumerate(captured) if 'CREATE INDEX' in s)
    assert create_index_idx > create_table_idx, 'CREATE INDEX should come after CREATE TABLE'

    # Verify secondary index uses bracket quoting
    index_sql = captured[create_index_idx]
    assert 'CREATE INDEX' in index_sql
    assert '[ix_single]' in index_sql
    assert '[name] ASC' in index_sql


@fact
@trait('unit', 'mssql')
def compound_secondary_index() -> None:
    @entity
    class CompoundIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        last_name: str = field(index='ix_user_composite')
        first_name: str = field(index='ix_user_composite')

    mock_connection, captured = _make_mock_connection()
    adapter = MSSQLTableAdapter[CompoundIndexEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    # First is SELECT COUNT(*) FROM sys.tables, second is CREATE TABLE, third is CREATE INDEX, fourth is SELECT from read()
    assert len(captured) >= 3
    create_index_idx = next(i for i, s in enumerate(captured) if 'CREATE INDEX' in s)

    index_sql = captured[create_index_idx]
    assert 'CREATE INDEX' in index_sql
    assert '[ix_user_composite]' in index_sql
    # Fields should be sorted alphabetically: first_name before last_name
    first_pos = index_sql.index('first_name')
    last_pos = index_sql.index('last_name')
    assert first_pos < last_pos, 'Fields should be alphabetically sorted'
    assert '[first_name] ASC' in index_sql
    assert '[last_name] ASC' in index_sql


@fact
@trait('unit', 'mssql')
def descending_secondary_index() -> None:
    @entity
    class DescIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        updated_at: str = field(
            index=IndexOptions(name='ix_desc', direction=IndexOrder.DESCENDING)
        )

    mock_connection, captured = _make_mock_connection()
    adapter = MSSQLTableAdapter[DescIndexEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    create_index_idx = next(i for i, s in enumerate(captured) if 'CREATE INDEX' in s)
    index_sql = captured[create_index_idx]
    assert 'CREATE INDEX' in index_sql
    assert '[ix_desc]' in index_sql
    assert '[updated_at] DESC' in index_sql


@fact
@trait('unit', 'mssql')
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
    adapter = MSSQLTableAdapter[MixedCompoundEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    create_index_idx = next(i for i, s in enumerate(captured) if 'CREATE INDEX' in s)
    index_sql = captured[create_index_idx]
    assert 'CREATE INDEX' in index_sql
    assert '[ix_mixed]' in index_sql
    assert '[first_name] ASC' in index_sql
    assert '[updated_at] DESC' in index_sql
    # Verify first_name comes before updated_at (alphabetically sorted)
    first_pos = index_sql.index('first_name')
    updated_pos = index_sql.index('updated_at')
    assert first_pos < updated_pos, 'Fields should be alphabetically sorted'


@fact
@trait('unit', 'mssql')
def no_secondary_indexes_only_create_table() -> None:
    @entity
    class NoSecondaryEntity:
        id: int = field(primary_key=True, autoincrement=True)
        name: str
        value: int

    mock_connection, captured = _make_mock_connection()
    adapter = MSSQLTableAdapter[NoSecondaryEntity](mock_connection, create_table=True)
    adapter.read(id=1)  # noqa: E501

    assert len(captured) >= 2
    create_table_idx = next(i for i, s in enumerate(captured) if 'CREATE TABLE' in s)
    # No CREATE INDEX should appear anywhere
    assert not any('CREATE INDEX' in s for s in captured)
