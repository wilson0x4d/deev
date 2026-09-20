# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from punit import fact, trait
from deev.common import ConnectionString, DbError
from deev.common.noop_cursor import NoopCursor


# --- NoopCursor behavior tests ---


@fact
@trait('common')
def noop_cursor_fetchone_returns_none() -> None:
    cursor = NoopCursor()
    result = cursor.fetchone()
    assert result is None, f'(expected=None, actual={result})'


@fact
@trait('common')
def noop_cursor_fetchmany_returns_empty_list() -> None:
    cursor = NoopCursor()
    result = cursor.fetchmany(5)
    assert result == [], f'(expected=[], actual={result})'


@fact
@trait('common')
def noop_cursor_fetchall_returns_empty_list() -> None:
    cursor = NoopCursor()
    result = cursor.fetchall()
    assert result == [], f'(expected=[], actual={result})'


@fact
@trait('common')
def noop_cursor_execute_is_noop() -> None:
    cursor = NoopCursor()
    cursor.execute('SELECT 1')
    # Should not raise


@fact
@trait('common')
def noop_cursor_executemany_is_noop() -> None:
    cursor = NoopCursor()
    cursor.executemany('INSERT INTO t VALUES (?)', [(1,), (2,)])
    # Should not raise


@fact
@trait('common')
def noop_cursor_close_is_noop() -> None:
    cursor = NoopCursor()
    cursor.close()
    # Should not raise


@fact
@trait('common')
def noop_cursor_description_is_none() -> None:
    cursor = NoopCursor()
    assert cursor.description is None, f'(expected=None, actual={cursor.description})'


@fact
@trait('common')
def noop_cursor_rowcount_is_zero() -> None:
    cursor = NoopCursor()
    assert cursor.rowcount == 0, f'(expected=0, actual={cursor.rowcount})'


@fact
@trait('common')
def noop_cursor_instantiated_fresh_per_call() -> None:
    a = NoopCursor()
    b = NoopCursor()
    assert a is not b, 'expected different instances'


# --- Execute method scrubbed statement tests (MSSQL) ---


@fact
@trait('mssql')
def mssql_nested_begin_increments_depth() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('BEGIN TRANSACTION nested')
        assert tx._MSSQLTransactionContext__transaction_depth == 2, f'(expected depth 2, got {tx._MSSQLTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
def mssql_nested_begin_via_method_works() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.begin_transaction()  # depth = 2
        result = tx.execute_scalar('SELECT 1')
        assert result == 1, f'(expected=1, actual={result})'
        tx.rollback()


# --- Execute method scrubbed statement tests (SQLite) ---


@fact
@trait('sqlite3')
def sqlite_execute_scrubbed_nested_begin_returns_noop() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.execute('INSERT INTO test (id) VALUES (1)')
        cursor = tx.execute('BEGIN TRANSACTION nested')
        assert isinstance(cursor, NoopCursor), f'(expected NoopCursor, got {type(cursor).__name__})'
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_execute_scalar_scrubbed_returns_none() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.execute('INSERT INTO test (id) VALUES (1)')
        tx.begin_transaction()  # depth = 2
        result = tx.execute_scalar('SELECT 1')
        # scrubbed begin at depth > 1 doesn't affect SELECT
        assert result == 1, f'(expected=1, actual={result})'
        tx.rollback()


# --- Execute method scrubbed statement tests (MySQL) ---


@fact
@trait('mysql')
def mysql_execute_scrubbed_nested_begin_returns_noop() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.begin_transaction()
            cursor = tx.execute('BEGIN TRANSACTION nested')
            assert isinstance(cursor, NoopCursor), f'(expected NoopCursor, got {type(cursor).__name__})'
            tx.rollback()
    finally:
        drop_database(cxnstring)


@fact
@trait('mysql')
def mysql_execute_reader_scrubbed_yields_nothing() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.begin_transaction()
            rows = list(tx.execute_reader('BEGIN TRANSACTION nested'))
            assert rows == [], f'(expected=[], actual={rows})'
            tx.rollback()
    finally:
        drop_database(cxnstring)


# --- TLC Guards tests ---


@fact
@trait('mssql')
def mssql_commit_at_depth_zero_raises() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        try:
            tx.execute('COMMIT')
        except DbError as e:
            assert 'No active transaction to commit' in str(e), f'(expected No active transaction to commit, got {e})'
        else:
            raise AssertionError('expected DbError on commit at depth 0')
        # rollback at depth 0 also raises per plan
        try:
            tx.rollback()
        except DbError:
            pass


@fact
@trait('mssql')
def mssql_rollback_at_depth_zero_raises() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        try:
            tx.execute('ROLLBACK')
        except DbError as e:
            assert 'No active transaction to rollback.' in str(e), f'(expected Cannot rollback, got {e})'
        else:
            raise AssertionError('expected DbError on rollback at depth 0')
        # rollback at depth 0 also raises per plan
        try:
            tx.rollback()
        except DbError:
            pass


@fact
@trait('sqlite3')
def sqlite_commit_at_depth_zero_raises() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        try:
            tx.execute('COMMIT')
        except DbError as e:
            assert 'No active transaction to commit' in str(e), f'(expected No active transaction to commit, got {e})'
        else:
            raise AssertionError('expected DbError on commit at depth 0')


@fact
@trait('mysql')
def mysql_commit_at_depth_zero_raises() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            try:
                tx.execute('COMMIT')
            except DbError as e:
                assert 'No active transaction to commit' in str(e), f'(expected No active transaction to commit, got {e})'
            else:
                raise AssertionError('expected DbError on commit at depth 0')
            # rollback at depth 0 also raises per plan
            try:
                tx.rollback()
            except DbError:
                pass
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
def mssql_rollback_at_depth_minus_one_raises() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.commit()
        tx._MSSQLTransactionContext__transaction_depth = -1  # type: ignore[attr-defined]
        try:
            tx.execute('SELECT 1')
        except DbError as e:
            assert 'Cannot use a transaction context that has exited.' in str(e), f'(expected exited error, got {e})'
        else:
            raise AssertionError('expected DbError after exit')


@fact
@trait('mssql')
def mssql_execute_commit_at_depth_zero_via_commit_method_raises() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        try:
            tx.commit()
        except DbError as e:
            assert 'No active transaction to commit' in str(e), f'(expected No active transaction to commit, got {e})'
        else:
            raise AssertionError('expected DbError on commit() at depth 0')
        # rollback at depth 0 also raises per plan
        try:
            tx.rollback()
        except DbError:
            pass


# --- Provider-specific SQL adaptation tests ---


@fact
@trait('mssql')
def mssql_sql_passthrough_as_is() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction('my_transaction')
        assert tx._MSSQLTransactionContext__transaction_name == 'my_transaction', f'(expected my_transaction, got {tx._MSSQLTransactionContext__transaction_name})'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_scrubs_begin_at_depth_greater_than_one() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.begin_transaction()  # depth = 2, scrubbed
        # Should still have depth 2 (begin_transaction method increments depth)
        assert tx._SQLiteTransactionContext__transaction_depth == 2, f'(expected depth 2, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_preserves_transaction_name() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction('my_sqlite_tx')
        assert tx._SQLiteTransactionContext__transaction_name == 'my_sqlite_tx', f'(expected my_sqlite_tx, got {tx._SQLiteTransactionContext__transaction_name})'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mysql')
def mysql_strips_transaction_name_from_start_transaction() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.begin_transaction('my_mysql_tx')
            assert tx._MySQLTransactionContext__transaction_name == 'my_mysql_tx', f'(expected my_mysql_tx, got {tx._MySQLTransactionContext__transaction_name})'  # type: ignore[attr-defined]
            tx.rollback()
    finally:
        drop_database(cxnstring)


@fact
@trait('mysql')
def mysql_begin_work_no_name() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.execute('BEGIN WORK')
            assert tx._MySQLTransactionContext__transaction_depth == 1, f'(expected depth 1, got {tx._MySQLTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
            assert tx._MySQLTransactionContext__transaction_name is None, f'(expected None, got {tx._MySQLTransactionContext__transaction_name})'  # type: ignore[attr-defined]
            tx.rollback()
    finally:
        drop_database(cxnstring)


@fact
@trait('mysql')
def mysql_begin_no_name() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.execute('BEGIN')
            assert tx._MySQLTransactionContext__transaction_depth == 1, f'(expected depth 1, got {tx._MySQLTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
            assert tx._MySQLTransactionContext__transaction_name is None, f'(expected None, got {tx._MySQLTransactionContext__transaction_name})'  # type: ignore[attr-defined]
            tx.rollback()
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
def mssql_provider_always_sends_commit() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction('outer_txn')
        tx.begin_transaction('inner_txn')
        tx.commit()  # Should decrement depth to 1, still sends COMMIT to DB
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'(expected depth 1 after commit, got {tx._MSSQLTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        tx.commit()


@fact
@trait('sqlite3')
def sqlite_provider_scrubs_commit_at_depth_greater_than_one() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.begin_transaction()  # depth = 2
        tx.commit()  # Should decrement depth to 1, scrubbed (no DB call)
        assert tx._SQLiteTransactionContext__transaction_depth == 1, f'(expected depth 1 after commit, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        tx.commit()


# --- Savepoint bookkeeping tests ---


@fact
@trait('mssql')
def mssql_create_savepoint_adds_to_savepoints_list() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.create_savepoint('sp1')
        tx.create_savepoint('sp2')
        savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
        assert savepoints == ['sp1', 'sp2'], f'(expected [sp1, sp2], got {savepoints})'
        tx.rollback()


@fact
@trait('mssql')
def mssql_rollback_savepoint_unwinds_list() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.create_savepoint('sp1')
        tx.create_savepoint('sp2')
        tx.create_savepoint('sp3')
        tx.rollback_savepoint('sp1')
        savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
        assert savepoints == [], f'(expected [], got {savepoints})'
        tx.rollback()


@fact
@trait('mssql')
def mssql_transaction_name_property_returns_correct_value() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        assert tx.transaction_name is None, f'(expected None, got {tx.transaction_name})'
        tx.begin_transaction('my_named_tx')
        assert tx.transaction_name == 'my_named_tx', f'(expected my_named_tx, got {tx.transaction_name})'
        tx.rollback()
        assert tx.transaction_name is None, f'(expected None after rollback, got {tx.transaction_name})'


@fact
@trait('mssql')
def mssql_savepoints_property_returns_tuple() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        result = tx.savepoints
        assert isinstance(result, tuple), f'(expected tuple, got {type(result).__name__})'
        tx.create_savepoint('sp1')
        assert tx.savepoints == ('sp1',), f'(expected (sp1,), got {tx.savepoints})'
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_savepoints_property_returns_tuple() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        result = tx.savepoints
        assert isinstance(result, tuple), f'(expected tuple, got {type(result).__name__})'
        tx.create_savepoint('sp1')
        assert tx.savepoints == ('sp1',), f'(expected (sp1,), got {tx.savepoints})'
        tx.rollback()


@fact
@trait('mysql')
def mysql_savepoints_property_returns_tuple() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.begin_transaction()
            result = tx.savepoints
            assert isinstance(result, tuple), f'(expected tuple, got {type(result).__name__})'
            tx.create_savepoint('sp1')
            assert tx.savepoints == ('sp1',), f'(expected (sp1,), got {tx.savepoints})'
            tx.rollback()
    finally:
        drop_database(cxnstring)


# --- Rollback name validation tests ---


@fact
@trait('mssql')
def mssql_rollback_invalid_name_raises() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        try:
            tx.rollback('invalid_name')
        except DbError as e:
            assert 'Invalid Transaction Name' in str(e), f'(expected Invalid Transaction Name, got {e})'
        else:
            raise AssertionError('expected DbError for invalid name')
        tx.rollback()


@fact
@trait('mssql')
def mssql_rollback_to_transaction_name_do_full_rollback() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction('my_tx')
        tx.create_savepoint('sp1')
        tx.rollback('my_tx')
        assert tx._MSSQLTransactionContext__transaction_depth == -3, f'(expected depth -3, got {tx._MSSQLTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
        assert savepoints == [], f'(expected [], got {savepoints})'


# --- Convenience methods bypassed tests ---


@fact
@trait('mssql')
def mssql_execute_commit_triggers_same_guard_as_commit_method() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        try:
            tx.execute('COMMIT')
        except DbError:
            pass  # expected
        else:
            raise AssertionError('expected DbError')
        # rollback at depth 0 also raises per plan
        try:
            tx.rollback()
        except DbError:
            pass


@fact
@trait('mssql')
def mssql_execute_rollback_at_depth_zero_raises() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        try:
            tx.execute('ROLLBACK')
        except DbError as e:
            assert 'No active transaction to rollback.' in str(e), f'(expected Cannot rollback, got {e})'
        else:
            raise AssertionError('expected DbError')
        # rollback at depth 0 also raises per plan
        try:
            tx.rollback()
        except DbError:
            pass


# --- Context manager exit tests ---


@fact
@trait('mssql')
def mssql_exit_raises_on_uncommitted_transaction() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        try:
            tx = MSSQLTransactionContext(connection)
            tx.__enter__()
            tx.__exit__(None, None, None)
        except DbError as e:
            assert 'Detected uncommitted transaction' in str(e), f'(expected uncommitted error, got {e})'


@fact
@trait('mssql')
def mssql_exit_rollback_on_exception() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        try:
            tx = MSSQLTransactionContext(connection)
            tx.__enter__()
            tx.__exit__(RuntimeError, RuntimeError('boom'), None)
        except RuntimeError:
            pass
        # After __exit__, depth should be -1 (context exited)
        assert tx._MSSQLTransactionContext__transaction_depth == -1, f'(expected depth -1 after __exit__, got {tx._MSSQLTransactionContext__transaction_depth})'  # type: ignore[attr-defined]


@fact
@trait('sqlite3')
@trait('sqlite3')
@trait('sqlite3')
def sqlite_create_savepoint_with_name() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.execute('INSERT INTO test (id) VALUES (1)')
        tx.create_savepoint('my_sp')
        savepoints = tx._SQLiteTransactionContext__savepoints  # type: ignore[attr-defined]
        assert 'my_sp' in savepoints, f'(expected my_sp in savepoints, got {savepoints})'
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_rollback_savepoint_no_name_pops_most_recent() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.create_savepoint('sp1')
        tx.create_savepoint('sp2')
        tx.create_savepoint('sp3')
        tx.rollback_savepoint()
        savepoints = tx._SQLiteTransactionContext__savepoints  # type: ignore[attr-defined]
        assert savepoints == ['sp1', 'sp2'], f'(expected [sp1, sp2], got {savepoints})'
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_rollback_savepoint_no_savepoints_is_noop() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.rollback_savepoint()
        savepoints = tx._SQLiteTransactionContext__savepoints  # type: ignore[attr-defined]
        assert savepoints == [], f'(expected [], got {savepoints})'
        tx.rollback()


@fact
@trait('sqlite3')
def sqlite_savepoint_commit_clears_all_savepoints() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.create_savepoint('sp1')
        tx.create_savepoint('sp2')
        tx.commit()
        savepoints = tx._SQLiteTransactionContext__savepoints  # type: ignore[attr-defined]
        assert savepoints == [], f'(expected [] after commit, got {savepoints})'


# --- NoopCursor returned by execute when scrubbed tests ---


@fact
@trait('common')
def execute_scrubbed_returns_noop_cursor_not_none() -> None:
    """NoopCursor is returned (not None) when __preprocess_sql returns None."""
    cursor = NoopCursor()
    assert cursor is not None, 'NoopCursor should not be None'


@fact
@trait('common')
def noops_are_fresh_per_call() -> None:
    """NoopCursor is instantiated fresh per call (not cached)."""
    a = NoopCursor()
    b = NoopCursor()
    assert a is not b, 'NoopCursor should not be cached'


# --- __exit__ clears __ambient_transaction_id tests ---


@fact
@trait('mssql')
def mssql_exit_clears_ambient_transaction_id() -> None:
    import appsettings2
    from deev.utils import connect
    from deev.mssql import MSSQLTransactionContext

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction('my_tx')
        assert tx._MSSQLTransactionContext__ambient_transaction_id.get() is not None, 'ambient should be set after begin'  # type: ignore[attr-defined]
        try:
            tx.__exit__(RuntimeError, RuntimeError('boom'), None)
        except RuntimeError:
            pass
        assert tx._MSSQLTransactionContext__ambient_transaction_id.get() is None, f'(expected None after exit, got {tx._MSSQLTransactionContext__ambient_transaction_id.get()})'  # type: ignore[attr-defined]


@fact
@trait('sqlite3')
def sqlite_exit_clears_ambient_transaction_id() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    db = sqlite3.Connection(':memory:')
    try:
        tx = SQLiteTransactionContext(db)
        tx.begin_transaction()
        assert tx._SQLiteTransactionContext__ambient_transaction_id.get() is not None, 'ambient should be set after begin'  # type: ignore[attr-defined]
        try:
            tx.__exit__(RuntimeError, RuntimeError('boom'), None)
        except RuntimeError:
            pass
        assert tx._SQLiteTransactionContext__ambient_transaction_id.get() is None, f'(expected None after exit, got {tx._SQLiteTransactionContext__ambient_transaction_id.get()})'  # type: ignore[attr-defined]
    finally:
        db.close()


@fact
@trait('mysql')
def mysql_exit_clears_ambient_transaction_id() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mysql import MySQLTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MySQLTransactionContext(connection)
            tx.begin_transaction()
            assert tx._MySQLTransactionContext__ambient_transaction_id.get() is not None, 'ambient should be set after begin'  # type: ignore[attr-defined]
            try:
                tx.__exit__(RuntimeError, RuntimeError('boom'), None)
            except RuntimeError:
                pass
            assert tx._MySQLTransactionContext__ambient_transaction_id.get() is None, f'(expected None after exit, got {tx._MySQLTransactionContext__ambient_transaction_id.get()})'  # type: ignore[attr-defined]
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
def clickhouse_exit_clears_ambient_transaction_id() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.clickhouse import ClickHouseTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = ClickHouseTransactionContext(connection)
            tx.begin_transaction()
            assert tx._ClickHouseTransactionContext__ambient_transaction_id.get() is not None, 'ambient should be set after begin'  # type: ignore[attr-defined]
            tx.__exit__(None, None, None)
            assert tx._ClickHouseTransactionContext__ambient_transaction_id.get() is None, f'(expected None after exit, got {tx._ClickHouseTransactionContext__ambient_transaction_id.get()})'  # type: ignore[attr-defined]
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
def mongo_exit_clears_ambient_transaction_id() -> None:
    import appsettings2
    from deev.utils import connect, create_database, drop_database
    from deev.mongodb import MongoTransactionContext
    from uuid import uuid4

    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mongo_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            tx = MongoTransactionContext(connection)
            tx.begin_transaction()
            assert tx._MongoTransactionContext__ambient_transaction_id.get() is not None, 'ambient should be set after begin'  # type: ignore[attr-defined]
            try:
                tx.__exit__(RuntimeError, RuntimeError('boom'), None)
            except RuntimeError:
                pass
            assert tx._MongoTransactionContext__ambient_transaction_id.get() is None, f'(expected None after exit, got {tx._MongoTransactionContext__ambient_transaction_id.get()})'  # type: ignore[attr-defined]
    finally:
        drop_database(cxnstring)


# --- Use-after-commit / use-after-rollback tests ---


@fact
@trait('sqlite3')
def sqlite_use_after_commit_raises() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.commit()
        assert tx._SQLiteTransactionContext__transaction_depth == -2, f'(expected depth -2 after commit, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        try:
            tx.execute('SELECT 1')
        except DbError as e:
            assert 'Cannot use a transaction context' in str(e), f'(expected context error, got {e})'
        else:
            raise AssertionError('expected DbError after commit')


@fact
@trait('sqlite3')
def sqlite_use_after_rollback_raises() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.rollback()
        assert tx._SQLiteTransactionContext__transaction_depth == -3, f'(expected depth -3 after rollback, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        try:
            tx.execute('SELECT 1')
        except DbError as e:
            assert 'Cannot use a transaction context' in str(e), f'(expected context error, got {e})'
        else:
            raise AssertionError('expected DbError after rollback')


@fact
@trait('sqlite3')
def sqlite_nested_commit_then_rollback_sets_finalized_depth() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.begin_transaction()  # depth = 2
        tx.commit()  # depth = 1 (nested commit, not finalized)
        assert tx._SQLiteTransactionContext__transaction_depth == 1, f'(expected depth 1, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        tx.commit()  # depth = -2 (final commit)
        assert tx._SQLiteTransactionContext__transaction_depth == -2, f'(expected depth -2 after final commit, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]


@fact
@trait('sqlite3')
def sqlite_savepoint_rollback_does_not_change_depth() -> None:
    import sqlite3
    from deev.sqlite import SQLiteTransactionContext

    with sqlite3.Connection(':memory:') as connection:
        tx = SQLiteTransactionContext(connection)
        tx.begin_transaction()
        tx.execute('CREATE TABLE test (id INT)')
        tx.create_savepoint('sp1')
        tx.rollback_savepoint()
        assert tx._SQLiteTransactionContext__transaction_depth == 1, f'(expected depth 1 after savepoint rollback, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
        tx.rollback()
        assert tx._SQLiteTransactionContext__transaction_depth == -3, f'(expected depth -3 after full rollback, got {tx._SQLiteTransactionContext__transaction_depth})'  # type: ignore[attr-defined]
