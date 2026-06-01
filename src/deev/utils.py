# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from typing import Any, Optional

from .common.ConnectionString import ConnectionString
from .common.DbConnection import DbConnection
from .common.DbContext import DbContext
from .common.DbError import DbError
from .common.DbMigrator import DbMigrator
from .common.DbTableAdapter import DbTableAdapter
from .common.DbTransactionContext import DbTransactionContext


def connect(connectionstring: ConnectionString | str) -> DbConnection:
    """
    Create a PEP 249 Connection to a database, given *connectionstring*.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    match connectionstring.provider:
        case 'mysql.connector' | 'mysql':
            from deev.mysql.MysqlProxyConnection import MysqlProxyConnection
            import mysql.connector
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 3306)
            return MysqlProxyConnection(mysql.connector.connect(
                host=host_name,
                port=port_number,
                user=connectionstring.user,
                password=connectionstring.password,
                database=connectionstring.database,
                use_pure=True
            ))
        case 'sqlite3' | 'sqlite':
            from deev.sqlite.SqliteProxyConnection import SqliteProxyConnection
            import sqlite3
            if connectionstring.database is None:
                raise ValueError('Missing `database` value in Connection String.')
            db_path = connectionstring.database if connectionstring.server is None else os.path.join(connectionstring.server, connectionstring.database)
            return SqliteProxyConnection(sqlite3.connect(db_path))
        case _:
            raise ValueError(f'Unsupported provider: {connectionstring.provider}')


def create_database(connectionstring: ConnectionString | str) -> None:
    """
    Create a database if it does not yet exist.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    if connectionstring.database is None:
        raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
    match connectionstring.provider:
        case 'mysql.connector' | 'mysql':
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            # make sure the target database exists, or create it if it doesn't exit yet
            import mysql.connector
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 3306)
            connection = mysql.connector.connect(
                host=host_name,
                port=port_number,
                user=connectionstring.user,
                password=connectionstring.password,
                use_pure=True
            )
            cursor = connection.cursor()
            cursor.execute(f'CREATE DATABASE IF NOT EXISTS {connectionstring.database};')
            cursor.close()
            connection.commit()
            connection.close()
        case 'sqlite3' | 'sqlite':
            # the only thing we do is ensure the target directory exists and make a connection attempt to validate
            if connectionstring.database is None:
                raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
            path = os.path.dirname(connectionstring.database if connectionstring.server is None else os.path.join(connectionstring.server, connectionstring.database))
            if len(path) > 0:
                os.makedirs(path, exist_ok=True)
            connect(connectionstring)
        case _:
            raise DbError(f'Unsupported database provider: {connectionstring.provider}')


def apply_migrations(connectionstring: ConnectionString, migrations_path: Optional[Path | str], stop_at: Optional[str] = None) -> None:
    if migrations_path is None and connectionstring.database is not None:
        migrations_path = os.path.join('.', 'migrations', connectionstring.database.lower())
    if migrations_path is not None:
        updater = DbMigrator(connectionstring)
        updater.apply(migrations_path, stop_at)
    else:
        raise ValueError('A value for `migrations_path` must be provided.')


def undo_migrations(
    connectionstring: ConnectionString,
    migrations_path: Optional[Path | str],
    stop_at: Optional[str] = None
) -> None:
    if migrations_path is None and connectionstring.database is not None:
        migrations_path = os.path.join('.', 'migrations', connectionstring.database.lower())
    if migrations_path is not None:
        updater = DbMigrator(connectionstring)
        updater.undo(migrations_path, stop_at)
    else:
        raise ValueError('A value for `migrations_path` must be provided.')


def create_table_adapter(
    entity_type: type,
    dbcontext_or_connectionstring: DbContext | ConnectionString,
    *,
    create_table: Optional[bool] = False,
    table_name: Optional[str] = None
) -> DbTableAdapter[Any]:
    dbcontext = (
        connect(dbcontext_or_connectionstring)
        if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
        else dbcontext_or_connectionstring
    )
    match type(dbcontext).__name__:
        case 'MysqlProxyConnection' | 'MySQLConnectionAbstract' | 'PooledMySQLConnection' | 'MysqlTransactionContext':
            import deev.mysql
            return deev.mysql.MysqlTableAdapter[entity_type](dbcontext, table_name=table_name, create_table=create_table)  # type: ignore[valid-type]
        case 'SqliteProxyConnection' | 'SqliteTransactionContext':
            import deev.sqlite
            return deev.sqlite.SqliteTableAdapter[entity_type](dbcontext, table_name=table_name, create_table=create_table)  # type: ignore[valid-type]
        case _:
            raise DbError(f'Unsupported object: {dbcontext}')


def begin_transaction(dbcontext_or_connectionstring: DbContext | ConnectionString) -> DbTransactionContext:
    dbcontext = (
        connect(dbcontext_or_connectionstring)
        if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
        else dbcontext_or_connectionstring
    )
    match type(dbcontext).__name__:
        case 'MysqlProxyConnection' | 'MySQLConnectionAbstract' | 'PooledMySQLConnection' | 'MysqlTransactionContext':
            import deev.mysql
            return deev.mysql.MysqlTransactionContext(dbcontext)
        case 'SqliteProxyConnection' | 'SqliteTransactionContext':
            import deev.sqlite
            return deev.sqlite.SqliteTransactionContext(dbcontext)
        case _:
            raise DbError(f'Unsupported object: {dbcontext}')


__all__ = [
    'begin_transaction',
    'connect',
    'create_database',
    'create_table_adapter',
    'apply_migrations',
    'undo_migrations'
]
