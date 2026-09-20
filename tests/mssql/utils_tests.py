# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database, drop_database
from deev.mssql import MSSQLProxyConnection
from uuid import uuid4
from punit import fact, trait


@fact
@trait('integration')
def cannot_connect_when_nonexistent_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    cxnstring.database = uuid4().hex
    try:
        with connect(cxnstring) as connection:
            connection.close()
    except Exception:
        pass
    else:
        assert False, f'expected failure for non-existent database: {cxnstring.database}'


@fact
@trait('integration')
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    drop_database(cxnstring)


@fact
@trait('integration')
def drop_database_is_idempotent() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    drop_database(cxnstring)
    drop_database(cxnstring)


@fact
@trait('integration')
def connect_after_create_database_works() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == 1
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
@trait('integration')
def connection_cursor_properties() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            assert isinstance(connection, MSSQLProxyConnection)
            cursor = connection.cursor()
            assert cursor is not None
            cursor.execute('SELECT @@VERSION as version')
            result = cursor.fetchone()
            assert result is not None
            cursor.close()
            connection.commit()
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
@trait('integration')
def connection_context_manager() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT 1 as one')
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == 1
            cursor.close()
    finally:
        drop_database(cxnstring)


@fact
@trait('mssql')
@trait('integration')
def connection_rollback_works() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_table = f'rolltest_{uuid4().hex[:8]}'
    with connect(cxnstring) as connection:
        cursor = connection.cursor()
        cursor.execute(f'CREATE TABLE [{unique_table}] ([id] INT IDENTITY(1,1), [val] NVARCHAR(100), PRIMARY KEY ([id]))')
        connection.commit()
        cursor.execute(f'INSERT INTO [{unique_table}] (val) VALUES (?)', ('before_rollback',))
        connection.rollback()
        cursor.execute(f'SELECT COUNT(*) FROM [{unique_table}]')
        count_result = cursor.fetchone()
        assert count_result is not None
        assert count_result[0] == 0
        cursor.close()
