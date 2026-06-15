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


def connect(
    connectionstring: ConnectionString | str,
    *,
    connect_timeout: int = 3,
    command_timeout: int = 9,
    **kwargs: Any
) -> DbConnection:
    """
    Create a PEP 249 Connection to a database, given *connectionstring*.

    Args:
        connectionstring: A DSN string or :class:`ConnectionString` object.
        connect_timeout: Connection timeout in seconds (if the provider supports it).
                            Only used when *connectionstring* does not specify
                            ``Connection Timeout``.
        command_timeout: Command/operation timeout in seconds (if the provider supports it).
                         Only used when *connectionstring* does not specify
                         ``Command Timeout``.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    effective_connect_timeout = connectionstring.connect_timeout if connectionstring.connect_timeout is not None else connect_timeout
    effective_command_timeout = connectionstring.command_timeout if connectionstring.command_timeout is not None else command_timeout
    match connectionstring.provider:
        case 'mongodb':
            from deev.mongodb.MongoProxyConnection import MongoProxyConnection
            import pymongo
            if connectionstring.database is None:
                raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
            # Use caller-provided authSource if given, otherwise resolve it automatically.
            effective_auth_source = kwargs.pop('authSource', None) or resolve_mongodb_auth_source(connectionstring)
            mongo_uri = f'mongodb://{connectionstring.user}:{connectionstring.password}@{connectionstring.server}/{connectionstring.database}'
            return MongoProxyConnection(
                pymongo.MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=effective_connect_timeout * 1000,
                    socketTimeoutMS=effective_command_timeout * 1000,
                    authSource=effective_auth_source,
                    **kwargs
                ),
                database_name=connectionstring.database
            )
        case 'mysql.connector' | 'mysql':
            from deev.mysql.MysqlProxyConnection import MysqlProxyConnection
            import mysql.connector
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 3306)
            conn = mysql.connector.connect(
                host=host_name,
                port=port_number,
                user=connectionstring.user,
                password=connectionstring.password,
                database=connectionstring.database,
                use_pure=True,
                connection_timeout=effective_connect_timeout,
                read_timeout=effective_command_timeout,
                write_timeout=effective_command_timeout
            )
            if effective_command_timeout is not None:
                cur = conn.cursor()
                cur.execute(f'SET SESSION wait_timeout={effective_command_timeout}')
                cur.close()
                conn.commit()
            return MysqlProxyConnection(conn)
        case 'sqlite3' | 'sqlite':
            from deev.sqlite.SqliteProxyConnection import SqliteProxyConnection
            import sqlite3
            if connectionstring.database is None:
                raise ValueError('Missing `database` value in Connection String.')
            db_path = connectionstring.database if connectionstring.server is None else os.path.join(connectionstring.server, connectionstring.database)
            return SqliteProxyConnection(sqlite3.connect(db_path))
        case _:
            raise ValueError(f'Unsupported provider: {connectionstring.provider}')


_MONGODB_AUTH_SOURCE_CACHE: dict[str, str] = {}


def resolve_mongodb_auth_source(connectionstring: ConnectionString) -> str:
    """
    Attempt to authenticate MongoDB user against each candidate authSource.

    Tries in order:
      1. ``connectionstring.database`` (the target database itself)
      2. ``'admin'``

    Results are cached by ``{server}:{database}:{user}`` key so subsequent calls
    with the same server/database/user return immediately without a network probe.

    Returns the first authSource that succeeds. Raises ``DbError`` if all fail.
    """
    import pymongo
    from pymongo import errors as _pymongo_errors

    cache_key = f"{connectionstring.server}:{connectionstring.database}:{connectionstring.user}"
    cached = _MONGODB_AUTH_SOURCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    candidates = []
    if connectionstring.database:
        candidates.append(connectionstring.database)
    candidates.append('admin')

    last_auth_error: Optional[Exception] = None
    for auth_source in candidates:
        mongo_uri = (
            f'mongodb://{connectionstring.user}:{connectionstring.password}'
            f'@{connectionstring.server}/{connectionstring.database}'
            f'?authSource={auth_source}'
        )
        try:
            client = pymongo.MongoClient(mongo_uri)  # type: ignore[var-annotated]
            client.list_database_names()  # forces real auth handshake
            return auth_source
        except _pymongo_errors.OperationFailure as e:
            if e.code == 18:  # AUTH_FAILED
                last_auth_error = e
                continue
            raise DbError(f'MongoDB connection error with authSource={auth_source}: {e}') from e
        except _pymongo_errors.PyMongoError as e:
            raise DbError(f'MongoDB connection error (server not reachable?): {e}') from e

    db_part = f'Database={connectionstring.database}' if connectionstring.database else 'no database'
    user_part = f'User={connectionstring.user}' if connectionstring.user else 'no user'
    err_detail = ''
    if isinstance(last_auth_error, _pymongo_errors.OperationFailure) and last_auth_error.code is not None:
        err_detail = f' (error code: {last_auth_error.code})'
    raise DbError(
        f'Could not authenticate MongoDB user with any authSource. '
        f'Tried authSource={", ".join(candidates)}. '
        f'{db_part}; {user_part}.{err_detail}'
    )


def create_database(connectionstring: ConnectionString | str) -> None:
    """
    Create a database if it does not yet exist.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    if connectionstring.database is None:
        raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
    match connectionstring.provider:
        case 'mongodb':
            auth_source = resolve_mongodb_auth_source(connectionstring)
            import pymongo
            mongo_client = pymongo.MongoClient(
                f'mongodb://{connectionstring.user}:{connectionstring.password}@{connectionstring.server}/{connectionstring.database}',
                authSource=auth_source
            )  # type: ignore[var-annotated]
            try:
                mongo_db = mongo_client[connectionstring.database]
                mongo_col_names = mongo_db.list_collection_names()
                if '_migrationdata' not in mongo_col_names:
                    mongo_col = mongo_db['_migrationdata']
                    mongo_col.insert_one({'id': 0, 'migration': '0'})
                    mongo_col.delete_one({'id': 0, 'migration': '0'})
            finally:
                mongo_client.close()
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
            try:
                cursor = connection.cursor()
                cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{connectionstring.database}`;')
                cursor.close()
                connection.commit()
            finally:
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


def apply_migrations(migration_name: str, connectionstring: ConnectionString, migrations_path: Optional[Path | str]) -> None:
    if migrations_path is None and connectionstring.database is not None:
        migrations_path = os.path.join('.', 'migrations', connectionstring.database.lower())
    if migrations_path is not None:
        updater = DbMigrator(connectionstring)
        updater.apply(migrations_path, migration_name)
    else:
        raise ValueError('A value for `migrations_path` must be provided.')


def undo_migrations(
    migration_name: str,
    connectionstring: ConnectionString,
    migrations_path: Optional[Path | str]
) -> None:
    if migrations_path is None and connectionstring.database is not None:
        migrations_path = os.path.join('.', 'migrations', connectionstring.database.lower())
    if migrations_path is not None:
        updater = DbMigrator(connectionstring)
        updater.undo(migrations_path, migration_name)
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
        case 'MongoProxyConnection' | 'MongoTransactionContext':
            import deev.mongodb
            return deev.mongodb.MongoTableAdapter[entity_type](dbcontext, table_name=table_name, create_table=create_table)  # type: ignore[valid-type]
        case _:
            raise DbError(f'Unsupported object: {dbcontext}')


def begin_transaction(dbcontext_or_connectionstring: DbContext | ConnectionString) -> DbTransactionContext:
    dbcontext = (
        connect(dbcontext_or_connectionstring)
        if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
        else dbcontext_or_connectionstring
    )
    match type(dbcontext).__name__:
        case 'MongoProxyConnection' | 'MongoTransactionContext':
            import deev.mongodb
            return deev.mongodb.MongoTransactionContext(dbcontext)
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
