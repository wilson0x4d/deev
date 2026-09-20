# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString, DbError
from deev.utils import connect
from deev.mssql import MSSQLTransactionContext
from uuid import uuid4
from punit import fact, trait


@fact
@trait('mssql')
@trait('integration')
def basic_verification() -> None:
    guid = uuid4().hex
    val = uuid4().hex
    unique_table = uuid4().hex[:8]
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as transaction:
            transaction.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            transaction.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (?, ?)', (guid, val))
            transaction.commit()

        with MSSQLTransactionContext(connection) as transaction:
            result = transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val
            transaction.commit()

        with MSSQLTransactionContext(connection) as transaction:
            val2 = uuid4().hex
            transaction.execute_nonquery(f'UPDATE [{unique_table}] SET val = ? WHERE id = ?', (val2, guid))
            transaction.commit()
        with MSSQLTransactionContext(connection) as transaction:
            result = transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val2
            transaction.commit()

        with MSSQLTransactionContext(connection) as transaction:
            val3 = uuid4().hex
            transaction.execute_nonquery(f'UPDATE [{unique_table}] SET val = ? WHERE id = ?', (val3, guid))
            transaction.rollback()
        with MSSQLTransactionContext(connection) as transaction:
            result = transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val2
            transaction.commit()

        with MSSQLTransactionContext(connection) as transaction:
            result = transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val2
            transaction.commit()
            with MSSQLTransactionContext(connection) as nested_transaction:
                nested_transaction.execute_nonquery(f'DELETE FROM [{unique_table}] WHERE id = ?', (guid,))
                nested_transaction.rollback()
        cursor = connection.cursor()
        cursor.execute(f'SELECT id FROM [{unique_table}] WHERE id = ?', (guid,))
        result = cursor.fetchone()
        assert result is not None


@fact
@trait('mssql')
@trait('integration')
def execute_returns_cursor() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = uuid4().hex[:8]
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as transaction:
            transaction.execute(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] NVARCHAR(100), PRIMARY KEY ([id]))')
            cursor = transaction.execute(f'INSERT INTO [{unique_table}] (val) VALUES (?)', ('hello',))
            assert cursor is not None
            transaction.commit()


@fact
@trait('mssql')
@trait('integration')
def test_basic_begin_commit() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            tx.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (?, ?)', (guid, val))
            tx.commit()

        with MSSQLTransactionContext(connection) as tx:
            result = tx.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val
            tx.commit()


@fact
@trait('mssql')
@trait('integration')
def test_multiple_executes_same_transaction() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.execute_scalar('SELECT 1')
            tx.execute_scalar('SELECT 2')
            tx.execute_scalar('SELECT COUNT(*) FROM sys.tables')
            tx.commit()


@fact
@trait('mssql')
@trait('integration')
def test_transaction_count_after_begin() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_transaction_count_after_commit() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.commit()
        assert tx._MSSQLTransactionContext__transaction_depth == -2, f'expected -2, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
def test_transaction_count_after_rollback() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        tx.rollback()
        assert tx._MSSQLTransactionContext__transaction_depth == -3, f'expected -3, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
def test_nested_begin_commit() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.begin_transaction()
            assert tx._MSSQLTransactionContext__transaction_depth == 2, f'expected 2, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
            tx.commit()
            assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
            tx.commit()


@fact
@trait('mssql')
@trait('integration')
def test_nested_begin_rollback() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.begin_transaction()
            assert tx._MSSQLTransactionContext__transaction_depth == 2, f'expected 2, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
            tx.rollback()
            assert tx._MSSQLTransactionContext__transaction_depth == -3, f'expected -3, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
def test_use_after_rollback_raises() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.rollback()
            try:
                tx.execute_scalar('SELECT 1')
            except DbError as e:
                assert 'Cannot use a transaction context' in str(e), f'Expected context error, got {e}'
            else:
                raise AssertionError('expected DbError after rollback')


@fact
@trait('mssql')
@trait('integration')
def test_savepoint_begin() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.create_savepoint()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1, f'expected 1 savepoint, got {len(savepoints)}'
            assert savepoints[0].startswith('TID_'), f'expected savepoint to start with TID_, got {savepoints[0]}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_savepoint_rollback() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = uuid4().hex[:8]
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] INT, PRIMARY KEY ([id]))')
            tx.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (1)')
            tx.create_savepoint()
            tx.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (2)')
            tx.rollback_savepoint()
            result = tx.execute_scalar(f'SELECT COUNT(*) FROM [{unique_table}]')
            assert result == 1, f'expected 1 row, got {result}'
            tx.commit()


@fact
@trait('mssql')
@trait('integration')
def test_savepoint_commit() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = uuid4().hex[:8]
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] INT, PRIMARY KEY ([id]))')
            tx.create_savepoint()
            tx.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (1)')
            tx.commit()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints after commit, got {len(savepoints)}'


@fact
@trait('mssql')
@trait('integration')
def test_savepoint_rollback_no_savepoints() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.rollback_savepoint()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints, got {len(savepoints)}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_aexit_auto_commit() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            tx.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (?, ?)', (guid, val))
            tx.commit()

        with MSSQLTransactionContext(connection) as tx:
            result = tx.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val
            tx.commit()


@fact
@trait('mssql')
@trait('integration')
def test_aexit_auto_rollback() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            tx.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (?, ?)', (guid, val))
            tx.commit()

        try:
            with MSSQLTransactionContext(connection) as tx:
                tx.execute_nonquery(f'UPDATE [{unique_table}] SET val = ? WHERE id = ?', (uuid4().hex, guid))
                raise RuntimeError('test exception')
        except RuntimeError:
            pass

        with MSSQLTransactionContext(connection) as tx:
            result = tx.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = ?', (guid,))
            assert result == val
            tx.commit()


@fact
@trait('mssql')
@trait('integration')
def test_aexit_noop_if_count_zero() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        # begin_transaction is called in __enter__, so depth would be 1
        # To test depth=0, we manually set it and skip __enter__
        tx._MSSQLTransactionContext__transaction_depth = 0  # type: ignore[attr-defined]
        # Manually call __exit__ without __enter__
        tx.__exit__(None, None, None)
        # Should not raise since depth is 0


@fact
@trait('mssql')
@trait('integration')
def test_execute_begin_transaction_increments_depth() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.execute_nonquery('BEGIN TRANSACTION')
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_execute_begin_tran_increments_depth() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.execute_nonquery('BEGIN TRAN')
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_execute_begin_transaction_named_sets_transaction_name() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.execute_nonquery('BEGIN TRANSACTION my_txn')
        assert tx._MSSQLTransactionContext__transaction_name == 'my_txn', f'expected `my_txn`, got {tx._MSSQLTransactionContext__transaction_name}'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_execute_begin_transaction_named_ignored_when_depth_gt_0() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction('tx_outer')
        assert tx._MSSQLTransactionContext__transaction_name == 'tx_outer', f'expected `tx_outer`, got` {tx._MSSQLTransactionContext__transaction_name}`'  # type: ignore[attr-defined]
        tx.execute_nonquery('BEGIN TRANSACTION tx_inner')
        assert tx._MSSQLTransactionContext__transaction_name == 'tx_outer', f'expected `tx_outer` to be preserved, got `{tx._MSSQLTransactionContext__transaction_name}`'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_execute_rollback_transaction_invalid_name_raises() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction()
        try:
            tx.execute_nonquery('ROLLBACK TRANSACTION nonexistent')
        except DbError as e:
            assert 'Invalid Transaction Name' in str(e)
        else:
            raise AssertionError('expected DbError for invalid transaction name')
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_rollback_savepoint_by_name_unwinds_above() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.create_savepoint('SP1')
            tx.create_savepoint('SP2')
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 2
            tx.rollback_savepoint('SP1')
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints after rollback to SP1, got {len(savepoints)}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_rollback_savepoint_no_name_uses_most_recent() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.create_savepoint()
            tx.create_savepoint()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 2
            tx.rollback_savepoint()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1, f'expected 1 savepoint after rollback_savepoint(), got {len(savepoints)}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_rollback_savepoint_no_savepoints_is_noop() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.rollback_savepoint()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints, got {len(savepoints)}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_execute_rollback_transaction_resets_depth() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.execute_nonquery('BEGIN TRANSACTION')
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.execute_nonquery('ROLLBACK TRANSACTION')
        assert tx._MSSQLTransactionContext__transaction_depth == -3, f'expected depth -3, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
def test_execute_commit_decrements_depth() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.execute_nonquery('BEGIN TRANSACTION')
        tx.execute_nonquery('BEGIN TRANSACTION')
        assert tx._MSSQLTransactionContext__transaction_depth == 2, f'expected depth 2, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.execute_nonquery('COMMIT')
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.execute_nonquery('COMMIT')
        assert tx._MSSQLTransactionContext__transaction_depth == -2, f'expected depth -2, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
def test_create_savepoint_with_name() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.create_savepoint('my_savepoint')
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1
            assert savepoints[0] == 'my_savepoint', f'expected my_savepoint, got {savepoints[0]}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_begin_transaction_method_with_name() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.begin_transaction('named_tx')
        assert tx._MSSQLTransactionContext__transaction_name == 'named_tx', f'expected `named_tx`, got `{tx._MSSQLTransactionContext__transaction_name}`'  # type: ignore[attr-defined]
        tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_rollback_to_savepoint_keyword() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.create_savepoint('sp1')
            tx.create_savepoint('sp2')
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 2
            tx.execute_nonquery('ROLLBACK TO SAVEPOINT sp1')
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints after ROLLBACK TO SAVEPOINT sp1, got {len(savepoints)}'
            tx.rollback()


@fact
@trait('mssql')
@trait('integration')
def test_rollback_short_form() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        tx = MSSQLTransactionContext(connection)
        tx.execute_nonquery('BEGIN TRAN')
        assert tx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        tx.execute_nonquery('ROLLBACK TRAN')
        assert tx._MSSQLTransactionContext__transaction_depth == -3, f'expected depth -3, got {tx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
def test_create_savepoint_auto_name_format() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        with MSSQLTransactionContext(connection) as tx:
            tx.create_savepoint()
            savepoints = tx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1
            assert savepoints[0].startswith('TID_'), f'expected savepoint to start with TID_, got {savepoints[0]}'
            assert len(savepoints[0]) == 28, f'expected 28 char savepoint name, got {len(savepoints[0])}'
            tx.rollback()
