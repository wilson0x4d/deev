# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.clickhouse import ClickHouseTransactionContext
from uuid import uuid4
from punit import fact, trait, sequential


@fact
@trait('clickhouse')
@trait('integration')
@sequential
def basic_verification() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            with ClickHouseTransactionContext(connection) as transaction:
                transaction.execute_nonquery(
                    'CREATE TABLE IF NOT EXISTS test (id String, val String) ENGINE = MergeTree() ORDER BY id'
                )
                transaction.execute_nonquery(
                    'INSERT INTO test (id, val) VALUES (%?, %?)',
                    (uuid4().hex, uuid4().hex)
                )
                transaction.commit()
            with ClickHouseTransactionContext(connection) as transaction:
                result = transaction.execute_scalar('SELECT val FROM test')
                assert result is not None
            with ClickHouseTransactionContext(connection) as transaction:
                val2 = uuid4().hex
                cursor = connection.cursor()
                cursor.execute('SELECT id FROM test LIMIT 1')
                row = cursor.fetchone()
            with ClickHouseTransactionContext(connection) as transaction:
                transaction.execute_nonquery(
                    'ALTER TABLE test DELETE WHERE 1 = 1',
                )
                transaction.commit()
            with ClickHouseTransactionContext(connection) as transaction:
                cursor = connection.cursor()
                cursor.execute('SELECT COUNT(*) FROM test')
                row = cursor.fetchone()
                assert row is not None
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass
