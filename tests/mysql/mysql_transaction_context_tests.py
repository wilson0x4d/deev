# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.mysql import MysqlTransactionContext
from uuid import uuid4
from punit import fact, trait, sequential


@fact
@trait('mysql')
@trait('integration')
@sequential
def basic_verification() -> None:
    guid = uuid4().hex
    val = uuid4().hex
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            # simple positive case, create a table and insert data, commit changes.
            with MysqlTransactionContext(connection) as transaction:
                transaction.execute_nonquery('CREATE TABLE IF NOT EXISTS test (id CHAR(32), val TEXT, PRIMARY KEY (id))')
                transaction.execute_nonquery('INSERT INTO test (id, val) VALUES (%?, %?)', (guid, val))
                transaction.commit()
            # confirm a read-only transaction does not require commit/rollback.
            with MysqlTransactionContext(connection) as transaction:
                result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
                assert result == val
            # confirm updates work
            with MysqlTransactionContext(connection) as transaction:
                val2 = uuid4().hex
                result = transaction.execute_scalar('UPDATE test SET val = %? WHERE id = %?', (val2, guid))
                transaction.commit()
            with MysqlTransactionContext(connection) as transaction:
                result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
                assert result == val2
            # confirm that we can update a record, rollback changes, and then read the original value back.
            with MysqlTransactionContext(connection) as transaction:
                val3 = uuid4().hex
                transaction.execute_nonquery('UPDATE test SET val = %? WHERE id = %?', (val3, guid))
                transaction.rollback()
            with MysqlTransactionContext(connection) as transaction:
                result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
                assert result == val2
            # confirm deletions can be rolled back
            with MysqlTransactionContext(connection) as transaction:
                transaction.execute_nonquery('DELETE FROM test WHERE id = %?', (guid,))
                transaction.rollback()
            # confirm transaction contexts can be nested
            with MysqlTransactionContext(connection) as transaction:
                result = transaction.execute_scalar('SELECT val FROM test WHERE id = %?', (guid,))
                assert result == val2
                # confirm deletions can be rolled back
                with MysqlTransactionContext(connection) as nested_transaction:
                    nested_transaction.execute_nonquery('DELETE FROM test WHERE id = %?', (guid,))
                    nested_transaction.rollback()
            cursor = connection.cursor()
            cursor.execute('SELECT id FROM test WHERE id = %s', (guid,))
            result = cursor.fetchone()
            assert result is not None
    finally:
        with connect(cxnstring) as connection:
            cursor = connection.cursor()
            cursor.execute(f'DROP DATABASE {cxnstring.database};')
            connection.commit()
            connection.close()
