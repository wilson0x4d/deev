# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.sqlite import SqliteTransactionContext
import sqlite3
from uuid import uuid4
from punit import fact, trait


@fact
@trait('integration')
@trait('sqlite3')
def basic_verification() -> None:
    guid = uuid4().hex
    val = uuid4().hex
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connectionStrings.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    with connect(cxnstring) as connection:
        # simple positive case, create a table and insert data, commit changes.
        with SqliteTransactionContext(connection) as transaction:
            transaction.execute_nonquery('CREATE TABLE IF NOT EXISTS test (id CHAR(32), val TEXT, PRIMARY KEY (id))')
            transaction.execute_nonquery('INSERT INTO test (id, val) VALUES (%?, %?)', (guid, val))
            transaction.commit()
        # confirm a read-only transaction does not require commit/rollback.
        with SqliteTransactionContext(connection) as transaction:
            result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
            assert result == val
        # confirm updates work
        with SqliteTransactionContext(connection) as transaction:
            val2 = uuid4().hex
            result = transaction.execute_scalar('UPDATE test SET val = %? WHERE id = %?', (val2, guid))
            transaction.commit()
        with SqliteTransactionContext(connection) as transaction:
            result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
            assert result == val2
        # confirm that we can update a record, rollback changes, and then read the original value back.
        with SqliteTransactionContext(connection) as transaction:
            val3 = uuid4().hex
            result = transaction.execute_nonquery('UPDATE test SET val = %? WHERE id = %?', (val3, guid))
            transaction.rollback()
        with SqliteTransactionContext(connection) as transaction:
            result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
            assert result == val2
        # confirm deletions can be rolled back
        with SqliteTransactionContext(connection) as transaction:
            transaction.execute_nonquery('DELETE FROM test WHERE id = %?', (guid,))
            transaction.rollback()
        # confirm transaction contexts can be nested
        with SqliteTransactionContext(connection) as transaction:
            result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
            assert result == val2
            # confirm deletions can be rolled back
            with SqliteTransactionContext(connection) as nested_transaction:
                nested_transaction.execute_nonquery('DELETE FROM test WHERE id = %?', (guid,))
                nested_transaction.rollback()
        cursor = connection.cursor()
        cursor.execute('SELECT id FROM test WHERE id = ?', (guid,))
        result = cursor.fetchone()
        assert result is not None


@fact
@trait('sqlite3')
def empty_commit_should_not_throw() -> None:
    with sqlite3.Connection(':memory:') as connection:
        with SqliteTransactionContext(connection) as transaction:
            transaction.execute_nonquery('SELECT 1')
            transaction.commit()


@fact
@trait('sqlite3')
def empty_rollback_should_not_throw() -> None:
    with sqlite3.Connection(':memory:') as connection:
        with SqliteTransactionContext(connection) as transaction:
            transaction.execute_nonquery('SELECT 1')
            transaction.rollback()

