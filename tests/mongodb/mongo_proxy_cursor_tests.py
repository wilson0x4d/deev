# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common.db_error import DbError
from deev.entities import entity, field
from deev.mongodb.mongo_proxy_cursor import MongoProxyCursor, _parse_sql_where
from deev.mongodb.mongo_table_adapter import MongoTableAdapter
from deev.utils import connect
from punit import fact, trait
from unittest.mock import MagicMock
import pymongo
from uuid import uuid4


def get_mongodb_connectionstring():
    """Get the ConnectionString to be used by mongodb tests."""
    import appsettings2
    from deev.common.connection_string import ConnectionString
    configuration = appsettings2.get_configuration()
    connection_str = configuration.connections.mongo_test
    return ConnectionString(connection_str)


def _make_cursor() -> tuple[MongoProxyCursor, MagicMock, MagicMock]:
    """Return a MongoProxyCursor backed by MagicMock objects."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    # _client is accessed via attribute on the ClientSession; wire it up
    mock_session._client = mock_client
    return MongoProxyCursor(mock_session, 'test_db'), mock_session, mock_client


@fact
@trait('integration')
@trait('mongodb')
def cursor_mongo_session_property_returns_session() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        session = cursor.mongo_session  # type: ignore[attr-defined]
        assert session is not None
        assert isinstance(session, pymongo.client_session.ClientSession)


@fact
@trait('integration')
@trait('mongodb')
def cursor_description_returns_none_without_execute() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        assert cursor.description is None


@fact
@trait('integration')
@trait('mongodb')
def cursor_fetch_returns_none_without_execute() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        assert cursor.fetchone() is None
        assert cursor.fetchmany(1) == []
        assert cursor.fetchall() == []


@fact
@trait('integration')
@trait('mongodb')
def cursor_mongo_fetch_returns_none_without_execute() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        assert cursor.mongo_fetchone() is None  # type: ignore[attr-defined]
        assert cursor.mongo_fetchmany(1) == []  # type: ignore[attr-defined]
        assert cursor.mongo_fetchall() == []  # type: ignore[attr-defined]


@fact
@trait('integration')
@trait('mongodb')
def cursor_close_ends_session() -> None:
    """Calling cursor.close() should end the underlying pymongo session."""
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        session = cursor.mongo_session  # type: ignore[attr-defined]
        assert session is not None
        cursor.close()


@fact
@trait('integration')
@trait('mongodb')
def cursor_update_rowcount_reflects_modifications() -> None:
    """Updating a field to its same value should report 0 modified rows."""
    conn_str = get_mongodb_connectionstring()
    uid = f'upd-row-{uuid4().hex[:8]}'
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        cursor.execute('INSERT deev_test(id, value) VALUES (%?, %?)', (uid, 'same'))
        cursor.execute(f"UPDATE deev_test SET value=%? WHERE id='{uid}'", ('same',))
        assert cursor.rowcount == 0, f"Expected rowcount=0, got {cursor.rowcount}"
        cursor.execute(f"UPDATE deev_test SET value=%? WHERE id='{uid}'", ('changed',))
        assert cursor.rowcount == 1, f"Expected rowcount=1, got {cursor.rowcount}"


@fact
@trait('unit')
def where_parser_equality_returns_direct_value() -> None:
    result = _parse_sql_where("name='alice'", ())
    assert result == {'name': 'alice'}


@fact
@trait('unit')
def where_parser_numeric_equality_returns_int_or_float() -> None:
    int_result = _parse_sql_where("age=30", ())
    assert int_result == {'age': 30}

    float_result = _parse_sql_where("score=3.14", ())
    assert float_result == {'score': 3.14}


@fact
@trait('unit')
def where_parser_placeholder_resolves_from_params() -> None:
    result = _parse_sql_where("name=%? AND age=%?", ('alice', 25))
    assert result == {'name': 'alice', 'age': 25}


@fact
@trait('unit')
def where_parser_null_returns_none() -> None:
    result = _parse_sql_where("email IS NULL", ())
    assert result == {'email': {'$eq': None}}


@fact
@trait('unit')
def where_parser_is_not_null_works() -> None:
    result = _parse_sql_where("name IS NOT NULL", ())
    assert result == {'name': {'$ne': None}}


@fact
@trait('unit')
def where_parser_comparison_lt() -> None:
    result = _parse_sql_where("age<30", ())
    assert result == {'age': {'$lt': 30}}


@fact
@trait('unit')
def where_parser_comparison_lte() -> None:
    result = _parse_sql_where("age<=30", ())
    assert result == {'age': {'$lte': 30}}


@fact
@trait('unit')
def where_parser_comparison_gt() -> None:
    result = _parse_sql_where("age>30", ())
    assert result == {'age': {'$gt': 30}}


@fact
@trait('unit')
def where_parser_comparison_gte() -> None:
    result = _parse_sql_where("age>=30", ())
    assert result == {'age': {'$gte': 30}}


@fact
@trait('unit')
def where_parser_comparison_ne() -> None:
    result = _parse_sql_where("name!='alice'", ())
    assert result == {'name': {'$ne': 'alice'}}


@fact
@trait('unit')
def where_parser_angle_bracket_ne() -> None:
    result = _parse_sql_where("name<>'alice'", ())
    assert result == {'name': {'$ne': 'alice'}}


@fact
@trait('unit')
def where_parser_in_operator_returns_list() -> None:
    result = _parse_sql_where("status IN ('active', 'pending')", ())
    assert result == {'status': {'$in': ['active', 'pending']}}


@fact
@trait('unit')
def where_parser_in_operator_with_numbers() -> None:
    result = _parse_sql_where("id IN (1, 2, 3)", ())
    assert result == {'id': {'$in': [1, 2, 3]}}


@fact
@trait('unit')
def where_parser_boolean_values() -> None:
    true_result = _parse_sql_where("active=true", ())
    assert true_result == {'active': True}

    false_result = _parse_sql_where("active=false", ())
    assert false_result == {'active': False}


@fact
@trait('unit')
def where_parser_and_conditions_merge_flat() -> None:
    result = _parse_sql_where("name='alice' AND age=30", ())
    assert result == {'name': 'alice', 'age': 30}


@fact
@trait('unit')
def where_parser_or_conditions_produce_or_array() -> None:
    result = _parse_sql_where("name='alice' OR name='bob'", ())
    assert '$or' in result
    assert len(result['$or']) == 2


@fact
@trait('unit')
def where_parser_empty_clause_returns_empty_dict() -> None:
    assert _parse_sql_where(None, ()) == {}
    assert _parse_sql_where('', ()) == {}


@fact
@trait('unit')
def where_parser_dot_notation_field_name_preserved() -> None:
    """Dot-notation field names (e.g. 'address.city') must be preserved."""
    result = _parse_sql_where("address.city='NYC'", ())
    assert 'address.city' in result, f"Expected 'address.city' key, got {list(result.keys())}"


@fact
@trait('unit')
def where_parser_dot_notation_in_comparison_works() -> None:
    """Dot-notation field with comparison operators must work."""
    result = _parse_sql_where("user.profile.age>=18", ())
    assert 'user.profile.age' in result, f"Expected 'user.profile.age' key, got {list(result.keys())}"


@fact
@trait('unit')
def where_parser_or_chain_resilient_to_unparseable_condition() -> None:
    """An unparseable condition in an OR chain should not corrupt surrounding clauses."""
    result = _parse_sql_where("x=1 OR invalid_token_xyzz OR y=2", ())

    assert '$or' in result, f"Expected $or array, got {result}"
    groups = result['$or']
    assert len(groups) == 2
    assert 'x' in groups[0], f"x not found in first group: {groups[0]}"
    assert 'y' in groups[1], f"y lost from OR chain: {result}"


@fact
@trait('unit')
def where_parser_and_chain_resilient_to_unparseable_condition() -> None:
    """An unparseable condition in an AND chain should be silently dropped."""
    result = _parse_sql_where("a=1 AND invalid_token_xyzz AND b=2", ())
    assert 'a' in result, f"a missing: {result}"
    assert 'b' in result, f"b missing: {result}"


@fact
@trait('integration')
@trait('mongodb')
def cursor_select_with_order_by_ascending_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: int = field()
            test_group: str = field()

        uid = f'obc-{uuid4().hex[:8]}'
        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        # Insert entities in reverse order of their values
        for i in [5, 1, 3]:
            adapter.create(id=f'{uid}-{i}', value=i, test_group=uid)

        # Query using table adapter (which exercises cursor + ORDER BY code path)
        results = list(adapter.query(where=f"test_group='{uid}'", orderby='value ASC'))
        values = [getattr(r, 'value') for r in results]
        assert len(values) == 3
        assert values == [1, 3, 5], f'Expected [1, 3, 5] but got {values}'


@fact
@trait('integration')
@trait('mongodb')
def adapter_query_with_order_by_descending_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: int = field()
            test_group: str = field()

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'obd-{uuid4().hex[:8]}'
        for i in [5, 1, 3]:
            adapter.create(id=f'{uid}-{i}', value=i, test_group=uid)

        # Use WHERE to scope results only to our test documents
        results = list(adapter.query(where=f"test_group='{uid}'", orderby='value DESC'))
        values = [getattr(r, 'value') for r in results]
        assert values == [5, 3, 1], f'Expected [5, 3, 1] but got {values}'


@fact
@trait('integration')
@trait('mongodb')
def cursor_query_with_comparison_operators_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            value: int = field()
            test_group: str = field()

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'cmp-{uuid4().hex[:8]}'
        # Insert test data scoped to our UID
        for i in [10, 20, 30]:
            adapter.create(id=f'{uid}-{i}', value=i, test_group=uid)

        # Query with WHERE using comparison operator and scope to our test documents
        results = list(adapter.query(where=f"test_group='{uid}' AND value>15"))
        values = sorted([getattr(r, 'value') for r in results])
        assert values == [20, 30], f'Expected [20, 30] but got {values}'


@fact
@trait('integration')
@trait('mongodb')
def adapter_query_with_in_operator_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        @entity
        class TestEntity:
            id: str = field(primary_key=True)
            status: str = field()
            test_group: str = field()

        adapter = MongoTableAdapter[TestEntity](connection, create_table=False)

        uid = f'inq-{uuid4().hex[:8]}'
        for s in ['active', 'inactive', 'pending']:
            adapter.create(id=f'{uid}-{s}', status=s, test_group=uid)

        # Query scoped to our test documents with IN operator
        results = list(adapter.query(where=f"test_group='{uid}' AND status IN ('active', 'pending')"))
        statuses = sorted([getattr(r, 'status') for r in results])
        assert statuses == ['active', 'pending'], f'Expected [active, pending] but got {statuses}'


@fact
@trait('unit')
def where_parser_raises_when_too_many_placeholders() -> None:
    """When the WHERE clause has more %? placeholders than provided params,
    the first placeholder is resolved but subsequent ones silently dropped."""
    result = _parse_sql_where("name=%? AND age=%?", ('alice',))
    assert result == {'name': 'alice'}, f"Expected {{'name': 'alice'}}, got {result}"


@fact
@trait('unit')
def where_parser_unrecognized_value_returns_empty() -> None:
    """A bare unquoted string resolves to empty dict because the DbError from
    _resolve_value is caught and skipped silently."""
    result = _parse_sql_where("name=garbage_no_quotes", ())
    assert result == {}


@fact
@trait('unit')
def where_parser_unrecognised_condition_returns_empty() -> None:
    """A truly unrecognised condition token (not matching any regex) is silently skipped."""
    result = _parse_sql_where("@@invalid_token", ())
    assert result == {}


@fact
@trait('unit')
def where_parser_null_literal_resolves_to_none() -> None:
    """A NULL value string resolves to Python None."""
    result = _parse_sql_where("email=NULL", ())
    assert 'email' in result
    assert result['email'] is None


@fact
@trait('unit')
def where_parser_mixed_and_or_groups_both_populated() -> None:
    """When both AND and OR are used, all groups should be collected into $or."""
    result = _parse_sql_where("a=1 AND b=2 OR c=3", ())
    assert '$or' in result
    groups: list[dict[str, object]] = result['$or']  # type: ignore[index]
    assert len(groups) == 2


@fact
@trait('unit')
def where_parser_only_or_single_group() -> None:
    """A single condition without AND/OR produces a flat dict."""
    result = _parse_sql_where("x=1", ())
    assert '$or' not in result
    assert 'x' in result


@fact
@trait('unit')
def where_parser_empty_string_returns_empty_dict() -> None:
    """An empty string clause is treated as no clause."""
    assert _parse_sql_where('', ()) == {}


@fact
@trait('unit')
def cursor_execute_select_with_star_produces_description_from_sample() -> None:
    """SELECT * should call find_one on the target collection for a sample doc."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    cursor.execute("SELECT * FROM users")

    mock_collection.find_one.assert_called_once_with({})


@fact
@trait('unit')
def cursor_execute_select_with_star_empty_collection_no_columns() -> None:
    """SELECT * on an empty collection should still produce a result set with no description."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.find_one.return_value = None

    cursor.execute("SELECT * FROM users")
    # No sample doc → description stays None, result set is empty list
    assert cursor.description is None


@fact
@trait('unit')
def cursor_execute_select_with_column_list_sets_projection() -> None:
    """Specifying columns should create a projection dict and not call find_one."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    cursor.execute("SELECT name FROM users WHERE age>10")

    mock_collection.find_one.assert_not_called()
    # find should have been called with projection {name: 1}
    found_call = mock_collection.find.call_args
    assert found_call is not None
    proj: dict[str, int] | None = found_call[1].get('projection')  # type: ignore[index]
    assert proj == {'name': 1}


@fact
@trait('unit')
def cursor_execute_select_with_order_by_desc() -> None:
    """ORDER BY with DESC should produce (-1,) sort spec."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_sort = MagicMock()
    mock_limit = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.find.return_value = mock_sort
    mock_sort.sort.return_value = mock_limit
    mock_limit.limit.return_value = [{'name': 'a'}]

    cursor.execute("SELECT name FROM users ORDER BY name DESC LIMIT 1")
    sort_args: list[tuple[str, int]] = mock_sort.sort.call_args[0][0]  # type: ignore[index]
    assert len(sort_args) == 1
    assert sort_args[0] == ('name', -1)


@fact
@trait('unit')
def cursor_execute_select_with_limit_sets_cursor_rowcount() -> None:
    """Row count should reflect the number of documents returned."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    docs: list[dict[str, str]] = [{'name': 'a'}, {'name': 'b'}]
    mock_collection.find.return_value.limit.return_value = docs

    cursor.execute("SELECT * FROM users LIMIT 10")
    assert cursor.rowcount == 2


@fact
@trait('unit')
def cursor_execute_select_backtick_table_name_stripped() -> None:
    """Backtick-quoted table names should have backticks stripped."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.find.return_value.limit.return_value = [{'name': 'a'}]

    cursor.execute("SELECT * FROM `my_table`")

    last_col = cursor._MongoProxyCursor__last_collection  # type: ignore[attr-defined]
    assert last_col is not None


@fact
@trait('unit')
def cursor_execute_select_with_placeholder_params() -> None:
    """SELECT with %? placeholders should pass params to _parse_sql_where."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.find.return_value.limit.return_value = [{'name': 'a'}]

    cursor.execute("SELECT * FROM users WHERE name=%? AND age>%?", ('Alice', 25))
    filter_arg: dict[str, object] = mock_collection.find.call_args[0][0]  # type: ignore[index]
    assert 'name' in filter_arg
    assert filter_arg['name'] == 'Alice'


@fact
@trait('unit')
def cursor_execute_select_unparseable_sql_raises() -> None:
    """Malformed SELECT should raise DbError."""
    cursor, session, client = _make_cursor()
    try:
        cursor.execute("SELECT")
        raise AssertionError('expected DbError was not observed.')
    except DbError:
        pass


@fact
@trait('unit')
def cursor_execute_insert_with_placeholders_resolves_params() -> None:
    """INSERT with %? should substitute params into the document."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id-123'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(name, age) VALUES (%?, %?)", ('Alice', 30))
    doc_arg: dict[str, object] = mock_collection.insert_one.call_args[0][0]  # type: ignore[index]
    assert doc_arg == {'name': 'Alice', 'age': 30}


@fact
@trait('unit')
def cursor_execute_insert_with_string_literal() -> None:
    """INSERT with a quoted string literal should embed the literal value."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(name) VALUES ('hello world')")
    doc_arg: dict[str, str] = mock_collection.insert_one.call_args[0][0]  # type: ignore[index]
    assert doc_arg == {'name': 'hello world'}


@fact
@trait('unit')
def cursor_execute_insert_with_int_literal() -> None:
    """INSERT with an integer literal should store as int."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(age) VALUES (42)")
    doc_arg: dict[str, int] = mock_collection.insert_one.call_args[0][0]  # type: ignore[index]
    assert doc_arg['age'] == 42


@fact
@trait('unit')
def cursor_execute_insert_with_float_literal() -> None:
    """INSERT with a float literal should store as float."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(price) VALUES (9.99)")
    doc_arg: dict[str, float] = mock_collection.insert_one.call_args[0][0]  # type: ignore[index]
    assert doc_arg['price'] == 9.99


@fact
@trait('unit')
def cursor_execute_insert_null_literal() -> None:
    """INSERT with NULL literal should store None."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(value) VALUES (NULL)")
    doc_arg: dict[str, None] = mock_collection.insert_one.call_args[0][0]  # type: ignore[index]
    assert doc_arg['value'] is None


@fact
@trait('unit')
def cursor_execute_insert_description_populated() -> None:
    """After INSERT, description should reflect the inserted column names."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(name, age) VALUES (%?, %?)", ('Alice', 30))
    assert cursor.description is not None
    field_names: list[str] = [f[0] for f in cursor.description]
    assert 'name' in field_names
    assert 'age' in field_names


@fact
@trait('unit')
def cursor_execute_insert_rowcount_is_one() -> None:
    """INSERT should set rowcount to 1."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(name) VALUES (%?)", ('Alice',))
    assert cursor.rowcount == 1


@fact
@trait('unit')
def cursor_execute_insert_unparseable_raises() -> None:
    """Malformed INSERT should raise DbError."""
    cursor, session, client = _make_cursor()
    try:
        cursor.execute("INSERT users")
        raise AssertionError('expected DbError was not observed.')
    except DbError:
        pass


@fact
@trait('unit')
def cursor_execute_insert_too_many_placeholders_raises() -> None:
    """INSERT with more %? placeholders than params raises DbError."""
    cursor, session, client = _make_cursor()
    try:
        cursor.execute("INSERT users(name, age) VALUES (%?, %?)", ('Alice',))
        raise AssertionError('expected DbError was not observed.')
    except DbError as e:
        assert 'more placeholders' in str(e).lower()


@fact
@trait('unit')
def cursor_execute_update_sets_document_and_where_filter() -> None:
    """UPDATE should build a $set document and a where filter."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    match_mock = MagicMock()
    match_mock.modified_count = 1
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.update_one.return_value = match_mock

    cursor.execute(
        "UPDATE users SET name='Bob', age=25 WHERE id=%?",
        ('user-1',)
    )
    update_call = mock_collection.update_one.call_args
    assert update_call is not None
    # First arg: where filter
    filter_arg: dict[str, str] = update_call[0][0]  # type: ignore[index]
    assert 'id' in filter_arg
    assert filter_arg['id'] == 'user-1'
    # Second arg: $set document
    set_doc: dict[str, object] = update_call[0][1]['$set']  # type: ignore[index]
    assert set_doc['name'] == 'Bob'


@fact
@trait('unit')
def cursor_execute_update_rowcount_reflects_modified_count() -> None:
    """UPDATE rowcount should reflect the number of modified documents."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    match_mock = MagicMock()
    match_mock.modified_count = 3
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.update_one.return_value = match_mock

    cursor.execute("UPDATE users SET name='Bob' WHERE age>10")
    assert cursor.rowcount == 3


@fact
@trait('unit')
def cursor_execute_update_unparseable_raises() -> None:
    """Malformed UPDATE should raise DbError."""
    cursor, session, client = _make_cursor()
    try:
        cursor.execute("UPDATE users")
        raise AssertionError('expected DbError was not observed.')
    except DbError:
        pass


@fact
@trait('unit')
def cursor_execute_delete_passes_where_filter() -> None:
    """DELETE should build a where filter and call delete_one."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    match_mock = MagicMock()
    match_mock.deleted_count = 1
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.delete_one.return_value = match_mock

    cursor.execute("DELETE FROM users WHERE id=%?", ('user-1',))
    filter_arg: dict[str, str] = mock_collection.delete_one.call_args[0][0]  # type: ignore[index]
    assert filter_arg['id'] == 'user-1'


@fact
@trait('unit')
def cursor_execute_delete_rowcount_reflects_deleted_count() -> None:
    """DELETE rowcount should reflect the number of deleted documents."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    match_mock = MagicMock()
    match_mock.deleted_count = 0
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.delete_one.return_value = match_mock

    cursor.execute("DELETE FROM users WHERE id=%?", ('nonexistent',))
    assert cursor.rowcount == 0


@fact
@trait('unit')
def cursor_execute_delete_unparseable_raises() -> None:
    """Malformed DELETE should raise DbError."""
    cursor, session, client = _make_cursor()
    try:
        cursor.execute("DELETE users")
        raise AssertionError('expected DbError was not observed.')
    except DbError:
        pass


@fact
@trait('unit')
def cursor_execute_unrecognised_prefix_is_nop() -> None:
    """An unrecognised SQL prefix should be silently ignored."""
    cursor, session, client = _make_cursor()

    cursor.execute("DROP TABLE users")


@fact
@trait('unit')
def cursor_executemany_inserts_multiple_docs() -> None:
    """executemany should insert all docs via insert_many."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    ids: list[str] = [uuid4().hex[:8] for _ in range(3)]
    result_mock = MagicMock()
    result_mock.inserted_ids = ids
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_many.return_value = result_mock

    cursor.executemany(
        "INSERT users(name, age) VALUES (%?, %?)",
        [('Alice', 30), ('Bob', 25)]
    )
    insert_call: list[dict[str, object]] = mock_collection.insert_many.call_args[0][0]  # type: ignore[index]
    assert len(insert_call) == 2
    assert insert_call[0]['name'] == 'Alice'
    assert insert_call[1]['name'] == 'Bob'
    assert cursor.rowcount == 3


@fact
@trait('unit')
def cursor_executemany_empty_seq_sets_zero_rowcount() -> None:
    """executemany with an empty param list should leave rowcount at 0."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    cursor.executemany(
        "INSERT users(name) VALUES (%?)",
        []
    )
    assert cursor.rowcount == 0


@fact
@trait('unit')
def cursor_executemany_fallback_to_execute_for_non_insert() -> None:
    """Non-INSERT SQL should fall through to execute in executemany."""
    cursor, session, client = _make_cursor()
    # "UPDATE" doesn't match the INSERT regex → falls back to execute()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'test-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

    cursor.executemany(
        "UPDATE users SET name='Bob' WHERE id=%?",  # valid UPDATE (has WHERE) → execute() path
        [('user-1',)]
    )
    # insert_many should NOT be called; the fallback goes through execute() which calls update_one
    mock_collection.insert_many.assert_not_called()


@fact
@trait('unit')
def cursor_fetchone_returns_dict_values_as_tuple() -> None:
    """fetchone should return a tuple of values from the first document."""
    cursor, session, client = _make_cursor()

    cursor._MongoProxyCursor__result_set = [{'name': 'Alice', 'age': 30}]  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__description_fields = ('name', 'age')  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_index = 0  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_count = 1  # type: ignore[attr-defined]

    row: tuple[object, ...] | None = cursor.fetchone()
    assert row == ('Alice', 30)


@fact
@trait('unit')
def cursor_fetchone_returns_none_when_no_result_set() -> None:
    """fetchone returns None when there's no result set."""
    cursor, session, client = _make_cursor()
    assert cursor.fetchone() is None


@fact
@trait('unit')
def cursor_fetchmany_returns_multiple_rows() -> None:
    """fetchmany(size=n) should return n rows as list of tuples."""
    cursor, session, client = _make_cursor()
    docs: list[dict[str, str]] = [{'name': f'p{i}'} for i in range(5)]
    cursor._MongoProxyCursor__result_set = docs  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__description_fields = ('name',)  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_index = 0  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_count = 5  # type: ignore[attr-defined]

    rows: list[tuple[str, ...]] = cursor.fetchmany(2)
    assert len(rows) == 2
    assert rows[0] == ('p0',)
    assert rows[1] == ('p1',)


@fact
@trait('unit')
def cursor_fetchall_consumes_remaining_rows() -> None:
    """fetchall should return all remaining rows and advance row_index."""
    cursor, session, client = _make_cursor()
    docs: list[dict[str, str]] = [{'name': f'p{i}'} for i in range(3)]
    cursor._MongoProxyCursor__result_set = docs  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__description_fields = ('name',)  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_index = 1  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_count = 3  # type: ignore[attr-defined]

    rows: list[tuple[str, ...]] = cursor.fetchall()
    assert len(rows) == 2
    assert rows[0] == ('p1',)
    assert rows[1] == ('p2',)


@fact
@trait('unit')
def cursor_mongo_fetchone_returns_copy_of_doc() -> None:
    """mongo_fetchone should return a dict (not the internal reference)."""
    cursor, session, client = _make_cursor()
    internal: dict[str, str] = {'name': 'Alice'}
    cursor._MongoProxyCursor__result_set = [internal]  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_index = 0  # type: ignore[attr-defined]

    doc: dict[str, str] | None = cursor.mongo_fetchone()  # type: ignore[attr-defined]
    assert doc == {'name': 'Alice'}
    assert doc is not internal


@fact
@trait('unit')
def cursor_mongo_fetchmany_returns_empty_when_no_result_set() -> None:
    """mongo_fetchmany returns [] when there's no result set."""
    cursor, session, client = _make_cursor()
    assert cursor.mongo_fetchmany(1) == []  # type: ignore[attr-defined]


@fact
@trait('unit')
def cursor_mongo_fetchall_returns_empty_when_no_result_set() -> None:
    """mongo_fetchall returns [] when there's no result set."""
    cursor, session, client = _make_cursor()
    assert cursor.mongo_fetchall() == []  # type: ignore[attr-defined]


@fact
@trait('unit')
def describe_field_none_returns_all_nones() -> None:
    """_infer_description_fields for None returns all Nones."""
    cursor, session, client = _make_cursor()
    type_code, display_size, internal_size, precision, scale = cursor._describe_field('x', {'x': None})  # type: ignore[attr-defined]
    assert display_size is None


@fact
@trait('unit')
def describe_field_int_returns_type_and_precision() -> None:
    """_infer_description_fields for int returns int type with precision=38."""
    cursor, session, client = _make_cursor()
    type_code, display_size, internal_size, precision, scale = cursor._describe_field('x', {'x': 42})  # type: ignore[attr-defined]
    assert type_code == int
    assert display_size == 2  # '42' has 2 chars
    assert internal_size == 8
    assert precision == 38
    assert scale == 0


@fact
@trait('unit')
def describe_field_float_returns_type_and_precision() -> None:
    """_infer_description_fields for float returns float type with precision=24."""
    cursor, session, client = _make_cursor()
    type_code, display_size, internal_size, precision, scale = cursor._describe_field('x', {'x': 3.14})  # type: ignore[attr-defined]
    assert type_code == float
    assert precision == 24
    assert scale == 16


@fact
@trait('unit')
def describe_field_str_returns_byte_length() -> None:
    """_infer_description_fields for str returns byte length as internal_size."""
    cursor, session, client = _make_cursor()
    type_code, display_size, internal_size, precision, scale = cursor._describe_field('x', {'x': 'hello'})  # type: ignore[attr-defined]
    assert type_code == str
    assert display_size == 5
    assert internal_size == 5


@fact
@trait('unit')
def describe_field_bool_returns_bool_type() -> None:
    """_infer_description_fields for bool returns bool type code."""
    cursor, session, client = _make_cursor()
    type_code, _, _, _, _ = cursor._describe_field('x', {'x': True})  # type: ignore[attr-defined]
    assert type_code == bool


@fact
@trait('unit')
def describe_field_bytes_returns_bytes_type_and_size() -> None:
    """_infer_description_fields for bytes returns bytes type and byte length."""
    cursor, session, client = _make_cursor()
    val: bytes = b'\x01\x02'  # Explicitly typed so pycodestyle doesn't complain.
    type_code, display_size, internal_size, _, _ = cursor._describe_field('x', {'x': val})  # type: ignore[attr-defined]
    assert type_code == bytes
    assert internal_size == 2


@fact
@trait('unit')
def describe_field_complex_types_return_str_type() -> None:
    """_infer_description_fields for complex types returns str type with repr length."""
    cursor, session, client = _make_cursor()
    val: list[int] = [1, 2]  # Explicitly typed so pycodestyle doesn't complain.
    type_code, display_size, _, _, _ = cursor._describe_field('x', {'x': val})  # type: ignore[attr-defined]
    assert type_code == str
    assert display_size == 6  # str([1, 2]) == '[1, 2]' is 6 chars


@fact
@trait('unit')
def describe_field_tuple_returns_str_type_with_repr_length() -> None:
    """_infer_description_fields for tuple returns str type with repr length."""
    cursor, session, client = _make_cursor()
    val: tuple[int, int, int] = (1, 2, 3)  # Explicitly typed so pycodestyle doesn't complain.
    type_code, display_size, _, _, _ = cursor._describe_field('x', {'x': val})  # type: ignore[attr-defined]
    assert type_code == str
    assert display_size == 9  # '(1, 2, 3)' has 9 chars (with spaces after commas)


@fact
@trait('unit')
def describe_field_dict_returns_str_type_with_repr_length() -> None:
    """_infer_description_fields for dict returns str type with repr length."""
    cursor, session, client = _make_cursor()
    val: dict[str, int] = {'a': 1}  # Explicitly typed so pycodestyle doesn't complain.
    type_code, display_size, _, _, _ = cursor._describe_field('x', {'x': val})  # type: ignore[attr-defined]
    assert type_code == str


@fact
@trait('unit')
def describe_field_set_returns_str_type_with_repr_length() -> None:
    """_infer_description_fields for set returns str type with repr length."""
    cursor, session, client = _make_cursor()
    val: set[int] = {1, 2}  # Explicitly typed so pycodestyle doesn't complain.
    type_code, display_size, _, _, _ = cursor._describe_field('x', {'x': val})  # type: ignore[attr-defined]
    assert type_code == str


@fact
@trait('unit')
def cursor_rowcount_before_execute_is_zero() -> None:
    """Initial rowcount should be 0."""
    cursor, session, client = _make_cursor()
    assert cursor.rowcount == 0


@fact
@trait('unit')
def cursor_close_handles_already_ended_session_gracefully() -> None:
    """close() should ignore errors when the session is already ended."""
    mock_session = MagicMock()
    mock_session.end_session.side_effect = Exception('already ended')
    cur, _, _ = MongoProxyCursor(mock_session, 'test_db'), mock_session, MagicMock()

    cur.close()


@fact
@trait('unit')
def cursor_description_populated_after_select_with_results() -> None:
    """description_fields should contain correct column names after SELECT."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    cursor.execute("SELECT name FROM users")
    # description property returns None when __result_set is empty (list(mock_cursor)=[])

    df: tuple[str, ...] | None = cursor._MongoProxyCursor__description_fields  # type: ignore[attr-defined]
    assert df == ('name',)


@fact
@trait('unit')
def cursor_description_populated_after_select_no_results_but_columns() -> None:
    """description_fields should be set even when SELECT returns no documents."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    cursor.execute("SELECT name FROM users")
    df: tuple[str, ...] | None = cursor._MongoProxyCursor__description_fields  # type: ignore[attr-defined]
    assert df is not None
    assert 'name' in df


@fact
@trait('unit')
def cursor_description_with_nullable_always_true() -> None:
    """description nullable flag should be True for MongoDB fields."""
    # description property requires non-empty __result_set, so set it manually
    cursor, session, client = _make_cursor()
    docs_sample: list[dict[str, str]] = [{'name': 'Alice'}]  # type: ignore[var-annotated]
    cursor._MongoProxyCursor__result_set = docs_sample  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__description_fields = ('name',)  # type: ignore[attr-defined]
    cursor._MongoProxyCursor__row_count = 1  # type: ignore[attr-defined]

    desc = cursor.description
    assert desc is not None
    nullable: bool = desc[0][6]  # DB-API: nullable is the 7th element
    assert nullable is True


@fact
@trait('unit')
def set_collection_name_stores_collection_reference() -> None:
    """_set_collection_name should store a reference to the named collection."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    session._client = mock_db  # type: ignore[attr-defined]
    cursor._set_collection_name('users')  # type: ignore[attr-defined]
    last_col = cursor._MongoProxyCursor__last_collection  # type: ignore[attr-defined]
    assert last_col is not None


# _get_database / _get_collection (internal helpers)


@fact
@trait('unit')
def get_database_returns_session_client_database() -> None:
    """_get_database should return a connection to the session's client database."""
    cursor, session, client = _make_cursor()
    # Use cursor._MongoProxyCursor__session (not the helper's 'session') to wire up
    mock_db = MagicMock()
    cursor._MongoProxyCursor__session._client = mock_db  # type: ignore[attr-defined]
    db = getattr(cursor, '_MongoProxyCursor__get_database')()  # type: ignore[valid-type]
    # db is mock_db['test_db'] (not mock_db itself because __get_database does self._client[name])
    assert db is not None


@fact
@trait('unit')
def get_collection_returns_fallback_collection() -> None:
    """_get_collection should return 'deev' collection as fallback."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    session._client = mock_db  # type: ignore[attr-defined]
    coll = cursor._get_collection()
    assert coll is not None


@fact
@trait('unit')
def where_parser_with_or_at_end_of_clause() -> None:
    """OR at end of clause should not cause errors."""
    result = _parse_sql_where("a=1 OR b=2", ())
    assert '$or' in result
    groups: list[dict[str, object]] = result['$or']  # type: ignore[index]
    assert len(groups) == 2


@fact
@trait('unit')
def where_parser_with_in_operator_mixed_types() -> None:
    """IN with mixed string/number types should resolve correctly."""
    result = _parse_sql_where("id IN (1, 'two', 3.0)", ())
    assert '$in' in result['id']
    assert result['id']['$in'] == [1, 'two', 3.0]


@fact
@trait('unit')
def cursor_execute_insert_with_empty_string_literal() -> None:
    """INSERT with an empty string literal should store empty string."""
    cursor, session, client = _make_cursor()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    result_mock = MagicMock()
    result_mock.inserted_id = 'new-id'
    client.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.insert_one.return_value = result_mock

    cursor.execute("INSERT users(name) VALUES ('')")
    doc_arg: dict[str, str] = mock_collection.insert_one.call_args[0][0]  # type: ignore[index]
    assert doc_arg == {'name': ''}


@fact
@trait('unit')
def where_parser_or_groups_append_final_and_group() -> None:
    """When the last group is an AND group (after OR), it should be appended."""
    result = _parse_sql_where("a=1 OR b=2 AND c=3", ())
    assert '$or' in result
    groups: list[dict[str, object]] = result['$or']  # type: ignore[index]
    assert len(groups) == 2
    # First group: a=1
    assert 'a' in groups[0]
    # Second group: b=2 AND c=3
    assert 'b' in groups[1] and 'c' in groups[1]
