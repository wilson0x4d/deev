# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString, DbError
from deev.utils import connect, connect_async
from deev.mssql.async_mssql_transaction_context import AsyncMSSQLTransactionContext
from uuid import uuid4
from punit import fact, trait, sequential


def get_mssql_connectionstring() -> ConnectionString:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    return cxnstring


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_commit_and_rollback() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex

    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            await transaction.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            await transaction.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (%?, %?)', (guid, val))
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            val2 = uuid4().hex
            await transaction.execute_nonquery(f'UPDATE [{unique_table}] SET val = %? WHERE id = %?', (val2, guid))
            await transaction.commit()
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val2
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            val3 = uuid4().hex
            await transaction.execute_nonquery(f'UPDATE [{unique_table}] SET val = %? WHERE id = %?', (val3, guid))
            await transaction.rollback()
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val2
            await transaction.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_nested_rollback() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex

    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            await transaction.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            await transaction.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (%?, %?)', (guid, val))
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await transaction.commit()
            async with AsyncMSSQLTransactionContext(connection) as nested_transaction:
                nested_val = uuid4().hex
                await nested_transaction.execute_nonquery(f'UPDATE [{unique_table}] SET val = %? WHERE id = %?', (nested_val, guid))
                await nested_transaction.rollback()
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await transaction.commit()
            assert result == val


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_reader() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = f'tbl_{uuid4().hex[:8]}'
    names = [f'item_{uuid4().hex[:4]}' for _ in range(3)]
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            await transaction.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [name] NVARCHAR(100), PRIMARY KEY ([id]))')
            for name in names:
                await transaction.execute_nonquery(f'INSERT INTO [{unique_table}] (name) VALUES (%?)', (name,))
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            results = []
            async for row in transaction.execute_reader(f'SELECT id, name FROM [{unique_table}] ORDER BY id'):
                results.append(row)
            assert len(results) == 3
            result_names = [row[1] for row in results]
            for name in names:
                assert name in result_names, f'Expected {name!r} in {result_names}'
            await transaction.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_cursor() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            await transaction.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] INT, PRIMARY KEY ([id]))')
            for i in range(1, 6):
                await transaction.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (%?)', (i,))
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            cursor = await transaction.cursor()
            await cursor.execute(f'SELECT val FROM [{unique_table}]')
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1
            rows = await cursor.fetchmany(2)
            assert len(rows) == 2
            assert rows[0][0] == 2
            assert rows[1][0] == 3
            remaining = await cursor.fetchall()
            assert len(remaining) == 2
            assert remaining[0][0] == 4
            assert remaining[1][0] == 5
            await transaction.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_exception_rollback() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex

    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            await transaction.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            await transaction.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (%?, %?)', (guid, val))
            await transaction.commit()

        try:
            async with AsyncMSSQLTransactionContext(connection) as transaction:
                await transaction.execute_nonquery(f'UPDATE [{unique_table}] SET val = %? WHERE id = %?', (uuid4().hex, guid))
                raise RuntimeError('test exception')
        except RuntimeError:
            pass

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await transaction.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_script() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    async with await connect_async(cxnstring) as connection:
        script = f"""
        CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [name] NVARCHAR(100), PRIMARY KEY ([id]));
        INSERT INTO [{unique_table}] (name) VALUES ('via_script');
        """
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            await transaction.execute_script(script)
            await transaction.commit()

        async with AsyncMSSQLTransactionContext(connection) as transaction:
            result = await transaction.execute_scalar(f'SELECT name FROM [{unique_table}] WHERE id = 1')
            assert result == 'via_script'
            await transaction.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_connection_property() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as transaction:
            assert transaction.connection is not None
            assert transaction.connection is connection
            await transaction.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_multiple_executes_same_transaction() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.execute_scalar('SELECT 1')
            await tx.execute_scalar('SELECT 2')
            await tx.execute_scalar('SELECT COUNT(*) FROM sys.tables')
            await tx.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_use_after_rollback_raises() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.rollback()
            try:
                await tx.execute_scalar('SELECT 1')
            except DbError as e:
                assert 'Cannot use a transaction context' in str(e), f'Expected context error, got {e}'
            else:
                raise AssertionError('expected DbError after rollback')


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_savepoint_begin() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints.clear()  # type: ignore[attr-defined]
            await tx.create_savepoint()
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1, f'expected 1 savepoint, got {len(savepoints)}'
            assert savepoints[0].startswith('TID_'), f'expected savepoint to start with TID_, got {savepoints[0]}'
            await tx.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_savepoint_rollback() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] INT, PRIMARY KEY ([id]))')
            await tx.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (1)')
            await tx.create_savepoint()
            await tx.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (2)')
            await tx.rollback_savepoint()
            result = await tx.execute_scalar(f'SELECT COUNT(*) FROM [{unique_table}]')
            assert result == 1, f'expected 1 row, got {result}'
            await tx.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_savepoint_commit() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] INT, PRIMARY KEY ([id]))')
            await tx.create_savepoint()
            await tx.execute_nonquery(f'INSERT INTO [{unique_table}] (val) VALUES (1)')
            await tx.commit()
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints after commit, got {len(savepoints)}'


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_savepoint_rollback_no_savepoints() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.rollback_savepoint()
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints, got {len(savepoints)}'
            await tx.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_aexit_auto_commit() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            await tx.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (%?, %?)', (guid, val))
            await tx.commit()

        async with AsyncMSSQLTransactionContext(connection) as tx:
            result = await tx.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await tx.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_aexit_auto_rollback() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_table = uuid4().hex[:8]
    guid = uuid4().hex
    val = uuid4().hex
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.execute_nonquery(f'CREATE TABLE [{unique_table}] ([id] CHAR(32), [val] NVARCHAR(MAX), PRIMARY KEY ([id]))')
            await tx.execute_nonquery(f'INSERT INTO [{unique_table}] (id, val) VALUES (%?, %?)', (guid, val))
            await tx.commit()

        try:
            async with AsyncMSSQLTransactionContext(connection) as tx:
                await tx.execute_nonquery(f'UPDATE [{unique_table}] SET val = %? WHERE id = %?', (uuid4().hex, guid))
                raise RuntimeError('test exception')
        except RuntimeError:
            pass

        async with AsyncMSSQLTransactionContext(connection) as tx:
            result = await tx.execute_scalar(f'SELECT val FROM [{unique_table}] WHERE id = %?', (guid,))
            assert result == val
            await tx.commit()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_aexit_noop_if_count_zero() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        # begin_transaction is called in __aenter__, so count would be 1
        # To test count=0, we manually set it and skip __aenter__
        # additionally, we check for None value due to a change in logic where inner_ctx alloc is deferred
        if tx._AsyncMSSQLTransactionContext__inner_ctx is not None:  # type: ignore[attr-defined]
            tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth = 0  # type: ignore[attr-defined]
        # Manually call __aexit__ without __aenter__
        await tx.__aexit__(None, None, None)
        # Should not raise since count is 0


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_begin_transaction_increments_depth() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.execute_nonquery('BEGIN TRANSACTION')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_begin_tran_increments_depth() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.execute_nonquery('BEGIN TRAN')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_rollback_transaction_invalid_name_raises() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.begin_transaction()
        try:
            await tx.execute_nonquery('ROLLBACK TRANSACTION nonexistent')
        except DbError as e:
            assert 'Invalid Transaction Name' in str(e)
        else:
            raise AssertionError('expected DbError for invalid transaction name')
        await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_rollback_savepoint_by_name_unwinds_above() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.create_savepoint('SP1')
            await tx.create_savepoint('SP2')
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 2
            await tx.rollback_savepoint('SP1')
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints after rollback to SP1, got {len(savepoints)}'
            await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_rollback_savepoint_no_name_uses_most_recent() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.create_savepoint()
            await tx.create_savepoint()
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 2
            await tx.rollback_savepoint()
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1, f'expected 1 savepoint after rollback_savepoint(), got {len(savepoints)}'
            await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_rollback_transaction_resets_depth() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.execute_nonquery('BEGIN TRANSACTION')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        await tx.execute_nonquery('ROLLBACK TRANSACTION')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == -3, f'expected depth -3, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_execute_commit_decrements_depth() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.execute_nonquery('BEGIN TRANSACTION')
        await tx.execute_nonquery('BEGIN TRANSACTION')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == 2, f'expected depth 2, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        await tx.execute_nonquery('COMMIT')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        await tx.execute_nonquery('COMMIT')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == -2, f'expected depth -2, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_create_savepoint_with_name() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.create_savepoint('my_savepoint')
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1
            assert savepoints[0] == 'my_savepoint', f'expected my_savepoint, got {savepoints[0]}'
            await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_begin_transaction_method_with_name() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.begin_transaction('named_tx')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_name == 'named_tx', f'expected `named_tx`, got `{tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_name}`'  # type: ignore[attr-defined]
        await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_rollback_to_savepoint_keyword() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.create_savepoint('sp1')
            await tx.create_savepoint('sp2')
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 2
            await tx.execute_nonquery('ROLLBACK TO SAVEPOINT sp1')
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 0, f'expected 0 savepoints after ROLLBACK TO SAVEPOINT sp1, got {len(savepoints)}'
            await tx.rollback()


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_rollback_short_form() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        tx = AsyncMSSQLTransactionContext(connection)
        await tx.execute_nonquery('BEGIN TRAN')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == 1, f'expected depth 1, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]
        await tx.execute_nonquery('ROLLBACK TRAN')
        assert tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth == -3, f'expected depth -3, got {tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__transaction_depth}'  # type: ignore[attr-defined]


@fact
@trait('mssql')
@trait('integration')
@sequential
async def async_transaction_create_savepoint_auto_name_format() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        async with AsyncMSSQLTransactionContext(connection) as tx:
            await tx.create_savepoint()
            savepoints = tx._AsyncMSSQLTransactionContext__inner_ctx._MSSQLTransactionContext__savepoints  # type: ignore[attr-defined]
            assert len(savepoints) == 1
            assert savepoints[0].startswith('TID_'), f'expected savepoint to start with TID_, got {savepoints[0]}'
            assert len(savepoints[0]) == 28, f'expected 28 char savepoint name, got {len(savepoints[0])}'
            await tx.rollback()
