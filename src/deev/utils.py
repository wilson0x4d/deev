# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from deev.sqlite import AsyncSqliteProxyConnection
import importlib
import os
import sys
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from .common.async_db_connection import AsyncDbConnection
from .common.async_db_table_adapter import AsyncDbTableAdapter
from .common.async_db_transaction_context import AsyncDbTransactionContext
from .common.connection_string import ConnectionString
from .common.db_connection import DbConnection
from .common.db_context import AsyncDbContext, DbContext
from .common.db_error import DbError
from .common.db_migrator import DbMigrator
from .common.db_table_adapter import DbTableAdapter
from .common.db_transaction_context import DbTransactionContext


def connect(
    connectionstring: ConnectionString | str,
    *,
    connect_timeout: int = 3,
    command_timeout: int = 9,
    **kwargs: Any
) -> DbConnection:
    """
    Create a PEP 249 :class:`DbConnection` to a database.

    Supported providers: ``sqlite3``, ``sqlite``, ``mysql.connector``, ``mongodb``, ``clickhouse``.

    :param connectionstring: A DSN string or :class:`ConnectionString` object.
    :param connect_timeout: Connection timeout in seconds. Only used when *connectionstring* does not specify ``Connection Timeout``.
    :param command_timeout: Command/operation timeout in seconds. Only used when *connectionstring* does not specify ``Command Timeout``.
    :return: A :class:`DbConnection` implementing PEP 249.
    :raises DbError: If the provider is unsupported or connection fails.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    effective_connect_timeout = connectionstring.connect_timeout if connectionstring.connect_timeout is not None else connect_timeout
    effective_command_timeout = connectionstring.command_timeout if connectionstring.command_timeout is not None else command_timeout
    match connectionstring.provider:
        case 'mongodb':
            from deev.mongodb.mongo_proxy_connection import MongoProxyConnection
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
                    uuidrepresentation='standard',
                    **kwargs
                ),
                database_name=connectionstring.database
            )
        case 'mysql.connector' | 'mysql':
            from deev.mysql.mysql_proxy_connection import MysqlProxyConnection
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
            from deev.sqlite.sqlite_proxy_connection import SqliteProxyConnection
            import sqlite3
            if connectionstring.database is None:
                raise ValueError('Missing `database` value in Connection String.')
            db_path = connectionstring.database if connectionstring.server is None else os.path.join(connectionstring.server, connectionstring.database)
            return SqliteProxyConnection(sqlite3.connect(db_path, check_same_thread=False))
        case 'clickhouse':
            from deev.clickhouse.clickhouse_proxy_connection import ClickHouseProxyConnection
            from clickhouse_connect.dbapi.connection import Connection as ClickHouseDBAPIConnection
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            if connectionstring.database is None:
                raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 8123)
            return ClickHouseProxyConnection(
                ClickHouseDBAPIConnection(
                    username=connectionstring.user or 'default',
                    password=connectionstring.password or '',
                    host=host_name,
                    database=connectionstring.database,
                    port=port_number,
                    compress=True,
                    connect_timeout=effective_connect_timeout,
                    send_receive_timeout=effective_command_timeout,
                    **kwargs
                )
            )
        case _:
            raise ValueError(f'Unsupported provider: {connectionstring.provider}')


async def connect_async(
    connectionstring: ConnectionString | str,
    *,
    connect_timeout: int = 3,
    command_timeout: int = 9,
    **kwargs: Any
) -> AsyncDbConnection:
    """
    Create a PEP 249 :class:`AsyncDbConnection` to a database.

    Supported providers: ``mongodb``, ``mysql.connector``, ``sqlite3``, ``sqlite``, ``clickhouse``.

    :param connectionstring: A DSN string or :class:`ConnectionString` object.
    :param connect_timeout: Connection timeout in seconds. Only used when *connectionstring* does not specify ``Connection Timeout``.
    :param command_timeout: Command/operation timeout in seconds. Only used when *connectionstring* does not specify ``Command Timeout``.
    :return: An :class:`AsyncDbConnection` implementing PEP 249.
    :raises DbError: If the provider is unsupported or connection fails.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    effective_connect_timeout = connectionstring.connect_timeout if connectionstring.connect_timeout is not None else connect_timeout
    effective_command_timeout = connectionstring.command_timeout if connectionstring.command_timeout is not None else command_timeout
    match connectionstring.provider:
        case 'mongodb':
            from deev.mongodb.async_mongo_proxy_connection import AsyncMongoProxyConnection
            import pymongo
            if connectionstring.database is None:
                raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
            # Use caller-provided authSource if given, otherwise resolve it automatically.
            effective_auth_source = kwargs.pop('authSource', None) or resolve_mongodb_auth_source(connectionstring)
            mongo_uri = f'mongodb://{connectionstring.user}:{connectionstring.password}@{connectionstring.server}/{connectionstring.database}'
            return AsyncMongoProxyConnection(
                pymongo.AsyncMongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=effective_connect_timeout * 1000,
                    socketTimeoutMS=effective_command_timeout * 1000,
                    authSource=effective_auth_source,
                    uuidrepresentation='standard',
                ),
                database_name=connectionstring.database,
                **kwargs
            )
        case 'mysql.connector' | 'mysql':
            from deev.mysql.async_mysql_proxy_connection import AsyncMysqlProxyConnection
            from mysql.connector.aio import connect
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 3306)
            return AsyncMysqlProxyConnection(
                await connect(
                    host=host_name,
                    port=port_number,
                    user=connectionstring.user,
                    password=connectionstring.password,
                    database=connectionstring.database,
                    use_pure=True,
                    connection_timeout=effective_connect_timeout,
                    read_timeout=effective_command_timeout,
                    write_timeout=effective_command_timeout,
                ),
                **kwargs
            )
        case 'sqlite3' | 'sqlite':
            from deev.sqlite.sqlite_proxy_connection import SqliteProxyConnection
            from deev.sqlite.async_sqlite_proxy_connection import AsyncSqliteProxyConnection
            import sqlite3
            if connectionstring.database is None:
                raise ValueError('Missing `database` value in Connection String.')
            db_path = connectionstring.database if connectionstring.server is None else os.path.join(connectionstring.server, connectionstring.database)
            return AsyncSqliteProxyConnection(sqlite3.connect(db_path))
        case 'clickhouse':
            from deev.clickhouse.async_clickhouse_proxy_connection import AsyncClickHouseProxyConnection
            import clickhouse_connect
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            if connectionstring.database is None:
                raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 8123)
            return AsyncClickHouseProxyConnection(
                await clickhouse_connect.get_async_client(
                    username=connectionstring.user or 'default',
                    password=connectionstring.password or '',
                    host=host_name,
                    port=port_number,
                    database=connectionstring.database,
                    connect_timeout=effective_connect_timeout,
                    send_receive_timeout=effective_command_timeout,
                ),
                **kwargs
            )
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

    last_auth_error: Exception | None = None
    for auth_source in candidates:
        mongo_uri = (
            f'mongodb://{connectionstring.user}:{connectionstring.password}'
            f'@{connectionstring.server}/{connectionstring.database}'
            f'?authSource={auth_source}'
        )
        try:
            client = pymongo.MongoClient(
                mongo_uri,
                uuidrepresentation='standard'
            )  # type: ignore[var-annotated]
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
    Create a database if it does not yet exist, and initialize migration tracking structures for supported providers.

    :param connectionstring: A DSN string or :class:`ConnectionString` object.
    :raises DbError: If the connection string is missing required components (database, server) or the provider is unsupported.
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
                authSource=auth_source,
                uuidrepresentation='standard'
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
        case 'clickhouse':
            from clickhouse_connect.driver import create_client
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 8123)
            clickhouse_client = create_client(
                host=host_name,
                username=connectionstring.user or 'default',
                password=connectionstring.password or '',
                port=port_number,
                compress=bool(connectionstring.parameters.get('compress', True)) is True,
                access_token=connectionstring.parameters.get('access_token', None),
            )
            try:
                cluster = connectionstring.parameters.get('cluster', None)
                on_cluster = '' if cluster is None else f' ON CLUSTER `{cluster}`'
                engine = connectionstring.parameters.get('engine', None)
                with_engine = '' if engine is None else f' ENGINE = {engine}'
                comment = connectionstring.parameters.get('comment', None)
                with_comment = '' if comment is None else f" COMMNENT = '{comment}'"
                clickhouse_client.command(f'CREATE DATABASE IF NOT EXISTS `{connectionstring.database}`{on_cluster}{with_engine}{with_comment}')
            finally:
                clickhouse_client.close()
        case _:
            raise DbError(f'Unsupported database provider: {connectionstring.provider}')


def drop_database(
    connectionstring: ConnectionString | str,
    cluster: str | None = None,
    *,
    connect_timeout: int = 15,
) -> None:
    """
    Drop a database if it exists. Safe to call multiple times.

    :param connectionstring: A DSN string or :class:`ConnectionString` object.
    :param cluster: ClickHouse cluster name.
    :param connect_timeout: Connection timeout in seconds.
                            Only used when *connectionstring* does not specify
                            ``Connection Timeout``.
    """
    if isinstance(connectionstring, str):
        connectionstring = ConnectionString(connectionstring)
    if connectionstring.database is None:
        raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
    cluster = connectionstring.parameters.get('cluster', None) if cluster is None else cluster
    effective_connect_timeout = connectionstring.connect_timeout if connectionstring.connect_timeout is not None else connect_timeout
    match connectionstring.provider:
        case 'mysql.connector' | 'mysql':
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            import mysql.connector
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 3306)
            connection = mysql.connector.connect(
                host=host_name,
                port=port_number,
                user=connectionstring.user,
                password=connectionstring.password,
                use_pure=True,
                connection_timeout=effective_connect_timeout
            )
            try:
                cursor = connection.cursor()
                cursor.execute(f'DROP DATABASE IF EXISTS `{connectionstring.database}`;')
                cursor.close()
            finally:
                connection.close()
        case 'mongodb':
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            auth_source = resolve_mongodb_auth_source(connectionstring)
            import pymongo
            mongo_client = pymongo.MongoClient(
                f'mongodb://{connectionstring.user}:{connectionstring.password}@{connectionstring.server}/',
                authSource=auth_source,
                uuidrepresentation='standard'
            )  # type: ignore[var-annotated]
            try:
                mongo_client.drop_database(connectionstring.database)
            finally:
                mongo_client.close()
        case 'sqlite3' | 'sqlite':
            if connectionstring.database is None:
                raise DbError(f'ConnectionString is missing `database` component: {connectionstring}')
            path = connectionstring.database if connectionstring.server is None else os.path.join(connectionstring.server, connectionstring.database)
            if os.path.exists(path):
                os.remove(path)
            wal_path = path + '-wal'
            shm_path = path + '-shm'
            for p in (wal_path, shm_path):
                if os.path.exists(p):
                    os.remove(p)
        case 'clickhouse':
            if connectionstring.server is None:
                raise DbError(f'ConnectionString is missing `server` component: {connectionstring}')
            from clickhouse_connect.driver import create_client
            parts = connectionstring.server.split(':')
            host_name, port_number = (parts[0], int(parts[1])) if len(parts) == 2 else (parts[0], 8123)
            clickhouse_client = create_client(
                host=host_name,
                username=connectionstring.user or 'default',
                password=connectionstring.password or '',
                port=port_number,
                compress=bool(connectionstring.parameters.get('compress', True)) is True,
                access_token=connectionstring.parameters.get('access_token', None),
            )
            try:
                cluster_clause = f' ON CLUSTER `{cluster}` SYNC' if cluster else ''
                clickhouse_client.command(f'DROP DATABASE IF EXISTS {connectionstring.database} {cluster_clause}')
            finally:
                clickhouse_client.close()
        case _:
            raise DbError(f'Unsupported database provider for drop: {connectionstring.provider}')


def apply_migrations(migration_name: str, connectionstring: ConnectionString, migrations_path: Path | str | None) -> None:
    """
    Apply database migrations from a directory.

    :param migration_name: Name of migration to stop at, or ``'all'``.
    :param connectionstring: Connection string for the target database.
    :param migrations_path: Path to migrations directory. Defaults to ``./migrations/{database_name}/``.
    :raises ValueError: If *migrations_path* is ``None`` and not derivable from *connectionstring*.
    """
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
    migrations_path: Path | str | None
) -> None:
    """
    Undo database migrations in reverse order.

    :param migration_name: Name of migration to stop at (undo up to and including this migration), or ``'all'``.
    :param connectionstring: Connection string for the target database.
    :param migrations_path: Path to migrations directory. Defaults to ``./migrations/{database_name}/``.
    :raises ValueError: If *migrations_path* is ``None`` and not derivable from *connectionstring*.
    """
    if migrations_path is None and connectionstring.database is not None:
        migrations_path = os.path.join('.', 'migrations', connectionstring.database.lower())
    if migrations_path is not None:
        updater = DbMigrator(connectionstring)
        updater.undo(migrations_path, migration_name)
    else:
        raise ValueError('A value for `migrations_path` must be provided.')


def generate_entity_ddl(
    dbcontext_or_connectionstring: DbContext | ConnectionString,
    entity_fqn: str
) -> list[str]:
    """
    Generate DDL statements for a given entity class.

    Resolves the entity type from the fully-qualified name, creates a connection,
    and generates DDL using the provider's DDL generator.

    :param dbcontext_or_connectionstring: A :class:`DbContext`, :class:`AsyncDbContext`, or :class:`ConnectionString`.
    :param entity_fqn: Fully-qualified entity class name (e.g. ``'myapp.entities.User'``).
    :return: List of DDL statement strings.
    :raises ValueError: If the entity type cannot be determined.
    :raises NotImplementedError: If the provider is MongoDB (not yet supported).
    :raises DbError: If the provider is unsupported.
    """
    entity_type: type | None = None
    if '.' in entity_fqn:
        module_path, _, class_name = entity_fqn.rpartition('.')
        try:
            module = importlib.import_module(module_path)
            entity_type = getattr(module, class_name, None)
        except ModuleNotFoundError:
            pass
    else:
        entity_type = globals().get(entity_fqn) or locals().get(entity_fqn)
    if entity_type is not None:
        from deev.entities import get_entity_spec
        entity_spec = get_entity_spec(entity_type)
        dbcontext = (
            connect(dbcontext_or_connectionstring)
            if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
            else dbcontext_or_connectionstring
        )
        match type(dbcontext).__name__:
            case 'MysqlProxyConnection' | 'MySQLConnectionAbstract' | 'PooledMySQLConnection' | 'MysqlTransactionContext':
                import deev.mysql
                mysql_ddl_generator = deev.mysql.MysqlDDLGenerator()
                return mysql_ddl_generator.generate_table_ddl(
                    entity_spec=entity_spec
                )
            case 'SqliteProxyConnection' | 'SqliteTransactionContext':
                import deev.sqlite
                sqlite_ddl_generator = deev.sqlite.SqliteDDLGenerator()
                return sqlite_ddl_generator.generate_table_ddl(
                    entity_spec=entity_spec
                )
            case 'MongoProxyConnection' | 'MongoTransactionContext':
                raise NotImplementedError('alpha feature, still not mongodb support.')
            case 'ClickHouseProxyConnection' | 'ClickHouseTransactionContext':
                import deev.clickhouse
                from deev.clickhouse.utils import resolve_clickhouse_table_engine
                
                engine = entity_spec.extra_args.get('engine')
                if engine is None:
                    db_engine = dbcontext.clickhouse_client.command(  # type: ignore[union-attr]
                        'SELECT engine_full FROM system.databases WHERE name = currentDatabase()'
                    )
                    engine = resolve_clickhouse_table_engine(str(db_engine).strip()) if db_engine else 'MergeTree'
                
                clickhouse_ddl_generator = deev.clickhouse.ClickHouseDDLGenerator()
                return clickhouse_ddl_generator.generate_table_ddl(
                    entity_spec=entity_spec,
                    engine=engine
                )
            case _:
                raise DbError(f'Unsupported object: {dbcontext}')
    else:
        raise ValueError(f'Cannot determine type information for `{entity_fqn}`.')


def generate_dbadapter_ddl(
    dbcontext_or_connectionstring: DbContext | ConnectionString,
    dbadapter_fqn: str
) -> list[str]:
    """
    Generate DDL statements for all entities referenced by a :class:`DbAdapter` subclass.

    Inspects the adapter class properties for ``DbTableAdapter[T]`` types and
    generates DDL for each entity type.

    :param dbcontext_or_connectionstring: A :class:`DbContext` or :class:`ConnectionString`.
    :param dbadapter_fqn: Fully-qualified ``DbAdapter`` subclass name.
    :return: List of DDL statement strings for all discovered entity types.
    :raises ValueError: If the adapter type cannot be determined.
    """
    dbadapter_type: type | None = None
    if '.' in dbadapter_fqn:
        module_path, _, class_name = dbadapter_fqn.rpartition('.')
        try:
            module = importlib.import_module(module_path)
            dbadapter_type = getattr(module, class_name, None)
        except ModuleNotFoundError:
            pass
    if dbadapter_type is None:
        raise ValueError(f'Cannot determine type information for `{dbadapter_fqn}`.')
    ddl: list[str] = []
    for name, attr in dbadapter_type.__dict__.items():
        if name.startswith('_'):
            continue
        if not isinstance(attr, property):
            continue
        fget = attr.fget
        if fget is None:
            continue
        try:
            mod = sys.modules[dbadapter_type.__module__]
            mod_globals = vars(mod)
            hints = get_type_hints(fget, globalns=mod_globals)
        except Exception:
            continue
        for hint in hints.values():
            origin = get_origin(hint)
            type_args = get_args(hint)
            if origin is not None and len(type_args) == 1:
                entity_type = type_args[0]
                if isinstance(entity_type, type) and issubclass(origin, DbTableAdapter):  # type: ignore[arg-type]
                    entity_ddl = generate_entity_ddl(
                        dbcontext_or_connectionstring,
                        f'{entity_type.__module__}.{entity_type.__name__}'
                    )
                    for stmt in entity_ddl:
                        ddl.append(stmt)
            break
    return ddl


def db_table_adapter_factory(
    entity_type: type,
    db_context: DbContext,
    *,
    create_table: bool | None = False,
    table_name: str | None = None,
    **kwargs: Any,
) -> DbTableAdapter[Any]:
    """
    Synchronous factory that creates the appropriate sync ``DbTableAdapter``
    for the given entity type and already-connected ``DbContext``.

    Provider detection is performed via ``type(db_context).__name__`` matching.
    This function does NOT call ``connect()`` — the caller must pass an
    already-established connection or transaction context.

    :param entity_type: The entity class.
    :param db_context: An already-connected :class:`DbContext`.
    :param create_table: Whether to create the table if it does not exist.
    :param table_name: Optional table name override.
    :param kwargs: Provider-specific options (e.g. ``sync_replicas=True`` for ClickHouse).
    :return: A :class:`DbTableAdapter[TEntity]`.
    :raises DbError: If the provider is unsupported.
    """
    match type(db_context).__name__:
        case 'ClickHouseProxyConnection' | 'ClickHouseTransactionContext':
            import deev.clickhouse
            kwargs['sync_replicas'] = True
            return deev.clickhouse.ClickHouseTableAdapter[entity_type](db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case 'MongoProxyConnection' | 'MongoTransactionContext':
            import deev.mongodb
            return deev.mongodb.MongoTableAdapter[entity_type](db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case 'MysqlProxyConnection' | 'MySQLConnectionAbstract' | 'PooledMySQLConnection' | 'MysqlTransactionContext':
            import deev.mysql
            return deev.mysql.MysqlTableAdapter[entity_type](db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case 'SqliteProxyConnection' | 'SqliteTransactionContext':
            import deev.sqlite
            return deev.sqlite.SqliteTableAdapter[entity_type](db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case _:
            raise DbError(f'Unsupported object: {db_context}')


def async_db_table_adapter_factory(
    entity_type: type,
    async_db_context: AsyncDbContext,
    *,
    create_table: bool | None = False,
    table_name: str | None = None,
    **kwargs: Any,
) -> AsyncDbTableAdapter[Any]:
    """
    Synchronous factory that creates the appropriate async ``AsyncDbTableAdapter``
    for the given entity type and already-connected ``AsyncDbContext``.

    The adapter **constructors** are synchronous — only the methods on them are async.
    Provider detection is performed via ``type(async_db_context).__name__`` matching.
    This function does NOT call ``connect_async()`` — the caller must pass an
    already-established connection or transaction context.

    :param entity_type: The entity class.
    :param async_db_context: An already-connected :class:`AsyncDbContext`.
    :param create_table: Whether to create the table if it does not exist.
    :param table_name: Optional table name override.
    :param kwargs: Provider-specific options.
    :return: A :class:`AsyncDbTableAdapter[TEntity]`.
    :raises DbError: If the provider is unsupported.
    """
    match type(async_db_context).__name__:
        case 'AsyncClickHouseProxyConnection' | 'AsyncClickHouseTransactionContext':
            import deev.clickhouse
            return deev.clickhouse.AsyncClickHouseTableAdapter[entity_type](async_db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case 'AsyncMongoProxyConnection' | 'AsyncMongoTransactionContext':
            import deev.mongodb
            return deev.mongodb.AsyncMongoTableAdapter[entity_type](async_db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case 'AsyncMysqlProxyConnection' | 'AsyncMysqlTransactionContext':
            import deev.mysql
            return deev.mysql.AsyncMysqlTableAdapter[entity_type](async_db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case 'AsyncSqliteProxyConnection' | 'AsyncSqliteTransactionContext':
            import deev.sqlite
            return deev.sqlite.AsyncSqliteTableAdapter[entity_type](async_db_context, table_name=table_name, create_table=create_table, **kwargs)  # type: ignore[arg-type, valid-type, return-value]
        case _:
            raise DbError(f'Unsupported object: {async_db_context}')


def create_table_adapter(
    entity_type: type,
    dbcontext_or_connectionstring: DbContext | ConnectionString,
    *,
    create_table: bool | None = False,
    table_name: str | None = None,
    **kwargs: Any
) -> DbTableAdapter[Any]:
    """
    Factory to create a :class:`DbTableAdapter` for the given entity type.

    Auto-detects the provider from the connection string or context and returns
    the appropriate provider-specific ``TableAdapter``.

    :param entity_type: The entity class.
    :param dbcontext_or_connectionstring: A :class:`DbContext` or :class:`ConnectionString`.
    :param create_table: Whether to create the table if it does not exist.
    :param table_name: Optional table name override.
    :param kwargs: Provider-specific options (e.g. ``sync_replicas=True`` for ClickHouse).
    :return: A :class:`DbTableAdapter[TEntity]`.
    :raises DbError: If the provider is unsupported.
    """
    dbcontext = (
        connect(dbcontext_or_connectionstring)
        if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
        else dbcontext_or_connectionstring
    )
    return db_table_adapter_factory(  # type: ignore[return-value]
        entity_type,
        dbcontext,
        create_table=create_table,
        table_name=table_name,
        **kwargs
    )


async def create_table_adapter_async(
    entity_type: type,
    dbcontext_or_connectionstring: AsyncDbContext | ConnectionString,
    *,
    create_table: bool | None = False,
    table_name: str | None = None,
    **kwargs: Any
) -> AsyncDbTableAdapter[Any]:
    """
    Async factory to create a :class:`AsyncDbTableAdapter` for the given entity type.

    Auto-detects the provider from the async connection context or connection string and returns
    the appropriate provider-specific ``AsyncTableAdapter``.

    :param entity_type: The entity class.
    :param dbcontext_or_connectionstring: An :class:`AsyncDbContext` or :class:`ConnectionString`.
    :param create_table: Whether to create the table if it does not exist.
    :param table_name: Optional table name override.
    :param kwargs: Provider-specific options.
    :return: A :class:`AsyncDbTableAdapter[TEntity]`.
    :raises DbError: If the provider is unsupported.
    """
    dbcontext = (
        await connect_async(dbcontext_or_connectionstring)
        if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
        else dbcontext_or_connectionstring
    )
    return async_db_table_adapter_factory(  # type: ignore[return-value]
        entity_type,
        dbcontext,
        create_table=create_table,
        table_name=table_name,
        **kwargs
    )


def begin_transaction(dbcontext_or_connectionstring: DbContext | ConnectionString) -> DbTransactionContext:
    """
    Begin a transaction on the given connection or context.

    :param dbcontext_or_connectionstring: A :class:`DbContext` or :class:`ConnectionString`.
    :return: A :class:`DbTransactionContext`.
    :raises DbError: If the provider is unsupported.
    """
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
        case 'ClickHouseProxyConnection' | 'ClickHouseTransactionContext':
            import deev.clickhouse
            return deev.clickhouse.ClickHouseTransactionContext(dbcontext)
        case _:
            raise DbError(f'Unsupported object: {dbcontext}')


async def begin_transaction_async(dbcontext_or_connectionstring: AsyncDbContext | ConnectionString) -> AsyncDbTransactionContext:
    """
    Begin an async transaction on the given connection or context.

    :param dbcontext_or_connectionstring: An :class:`AsyncDbContext` or :class:`ConnectionString`.
    :return: An :class:`AsyncDbTransactionContext`.
    :raises DbError: If the provider is unsupported.
    """
    dbcontext = (
        (await connect_async(dbcontext_or_connectionstring))
        if isinstance(dbcontext_or_connectionstring, (ConnectionString, str))
        else dbcontext_or_connectionstring
    )
    match type(dbcontext).__name__:
        case 'AsyncMongoProxyConnection' | 'AsyncMongoTransactionContext':
            import deev.mongodb
            return deev.mongodb.AsyncMongoTransactionContext(dbcontext)
        case 'AsyncMysqlProxyConnection' | 'AsyncMysqlTransactionContext':
            import deev.mysql
            return deev.mysql.AsyncMysqlTransactionContext(dbcontext)
        case 'AsyncSqliteProxyConnection' | 'AsyncSqliteTransactionContext':
            import deev.sqlite
            return deev.sqlite.AsyncSqliteTransactionContext(dbcontext)
        case 'AsyncClickHouseProxyConnection' | 'AsyncClickHouseTransactionContext':
            import deev.clickhouse
            return deev.clickhouse.AsyncClickHouseTransactionContext(dbcontext)
        case _:
            raise DbError(f'Unsupported object: {dbcontext}')

__all__ = [
    'apply_migrations',
    'async_db_table_adapter_factory',
    'begin_transaction',
    'begin_transaction_async',
    'connect',
    'connect_async',
    'create_database',
    'create_table_adapter',
    'create_table_adapter_async',
    'db_table_adapter_factory',
    'generate_dbadapter_ddl',
    'generate_entity_ddl',
    'resolve_mongodb_auth_source',
    'undo_migrations',
]
