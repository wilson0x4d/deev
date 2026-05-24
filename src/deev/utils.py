# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from typing import Optional

from .common.ConnectionString import ConnectionString
from .common.DbConnection import DbConnection
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
            return MysqlProxyConnection(mysql.connector.connect(
                host=connectionstring.server,
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
            hostName, portNumber = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 3306)
            connection = mysql.connector.connect(
                host=hostName,
                port=portNumber,
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


def undo_migrations(connectionstring: ConnectionString, migrations_path: Optional[Path | str], stop_at: Optional[str] = None) -> None:
    if migrations_path is None and connectionstring.database is not None:
        migrations_path = os.path.join('.', 'migrations', connectionstring.database.lower())
    if migrations_path is not None:
        updater = DbMigrator(connectionstring)
        updater.undo(migrations_path, stop_at)
    else:
        raise ValueError('A value for `migrations_path` must be provided.')


def get_table_adapter(entity_type: type, connectionstring: ConnectionString) -> DbTableAdapter:
    match connectionstring.provider:
        case 'mysql.connector' | 'mysql':
            import deev.mysql
            return deev.mysql.MysqlTableAdapter[entity_type](connect(connectionstring))  # type: ignore[valid-type]
        case 'sqlite3' | 'sqlite':
            import deev.sqlite
            return deev.sqlite.SqliteTableAdapter[entity_type](connect(connectionstring))  # type: ignore[valid-type]
        case _:
            raise DbError(f'Unsupported database provider: {connectionstring.provider}')


def get_transaction_context(connectionstring: ConnectionString) -> DbTransactionContext:
    match connectionstring.provider:
        case 'mysql.connector' | 'mysql':
            import deev.mysql
            return deev.mysql.MysqlTransactionContext(connect(connectionstring))
        case 'sqlite3' | 'sqlite':
            import deev.sqlite
            return deev.sqlite.SqliteTransactionContext(connect(connectionstring))
        case _:
            raise DbError(f'Unsupported database provider: {connectionstring.provider}')


__all__ = [
    'connect',
    'create_database',
    'get_table_adapter',
    'get_transaction_context',
    'apply_migrations',
    'undo_migrations'
]
