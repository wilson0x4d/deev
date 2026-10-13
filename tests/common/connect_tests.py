# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import asyncio
import tempfile
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch
)

from punit import fact, raises

from deev.sqlite.async_sqlite_proxy_connection import AsyncSQLiteProxyConnection
from deev.sqlite.sqlite_proxy_connection import SQLiteProxyConnection
from deev.utils import (
    connect,
    connect_async
)
from pymongo.errors import ConfigurationError


def _sqlite_connectionstring(tmpdir: str) -> str:
    return f'Server={tmpdir};Database=kw.db;Provider=sqlite3'


@fact
def sqlite_connect_forwards_kwargs_to_driver() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        with connect(_sqlite_connectionstring(tmpdir), isolation_level=None) as connection:
            assert isinstance(connection, SQLiteProxyConnection), f'expected SQLiteProxyConnection, got {type(connection)}'
            isolation_level = connection.sqlite_connection.isolation_level
            assert isolation_level is None, f'(expected=None, actual={isolation_level})'


@fact
def sqlite_connect_rejects_unknown_driver_kwargs() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        assert raises[TypeError](lambda: connect(_sqlite_connectionstring(tmpdir), bogus_kwarg=1))


@fact
async def sqlite_connect_async_forwards_kwargs_to_driver() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        async with await connect_async(_sqlite_connectionstring(tmpdir), isolation_level=None) as connection:
            assert isinstance(connection, AsyncSQLiteProxyConnection), f'expected AsyncSQLiteProxyConnection, got {type(connection)}'
            isolation_level = connection.sqlite_connection.sqlite_connection.isolation_level
            assert isolation_level is None, f'(expected=None, actual={isolation_level})'


@fact
async def sqlite_connect_async_rejects_unknown_driver_kwargs() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        def _run() -> bool:
            return bool(raises[TypeError](
                lambda: asyncio.run(connect_async(_sqlite_connectionstring(tmpdir), bogus_kwarg=1))
            ))

        result = _run()
        assert result is True, 'connect_async should raise TypeError for unknown driver kwargs'


@fact
def mongodb_connect_forwards_kwargs_to_driver() -> None:
    connection = connect('mongodb://user:pass@localhost:27017/kwtest', authSource='admin', tz_aware=True)
    try:
        mongo_client = getattr(connection, 'mongo_client', None)
        assert mongo_client is not None, 'mongo_client property should exist'
        tz_aware = mongo_client.codec_options.tz_aware
        assert tz_aware is True, f'(expected=True, actual={tz_aware})'
    finally:
        connection.close()


@fact
def mongodb_connect_rejects_unknown_driver_kwargs() -> None:
    assert raises[ConfigurationError](
        lambda: connect('mongodb://user:pass@localhost:27017/kwtest', authSource='admin', bogus_option=1)
    )


@fact
async def mongodb_connect_async_forwards_kwargs_to_driver() -> None:
    connection = await connect_async('mongodb://user:pass@localhost:27017/kwtest', authSource='admin', tz_aware=True)
    try:
        mongo_client = getattr(connection, 'mongo_client', None)
        assert mongo_client is not None, 'mongo_client property should exist'
        tz_aware = mongo_client.codec_options.tz_aware
        assert tz_aware is True, f'(expected=True, actual={tz_aware})'
    finally:
        await connection.close()


@fact
def mysql_connect_forwards_kwargs_to_driver() -> None:
    mock_connection = MagicMock()
    with patch('mysql.connector.connect', MagicMock(return_value=mock_connection)) as mock_connect:
        with connect('mysql://root:secret@localhost:3307/kwtest', get_warnings=True) as connection:
            mock_connect.assert_called_with(
                host='localhost',
                port=3307,
                user='root',
                password='secret',
                database='kwtest',
                use_pure=True,
                connection_timeout=3,
                read_timeout=9,
                write_timeout=9,
                get_warnings=True
            )
            assert mock_connect.called, 'mysql.connector.connect should have been called'
        assert mock_connection.commit.called, 'connection.commit should have been called after SET SESSION'


@fact
async def mysql_connect_async_forwards_kwargs_to_driver() -> None:
    mock_connection = MagicMock()
    mock_connection.close = AsyncMock()
    mock_connect = AsyncMock(return_value=mock_connection)
    with patch('mysql.connector.aio.connect', mock_connect):
        connection = await connect_async('mysql://root:secret@localhost:3307/kwtest', get_warnings=True)
        try:
            mock_connect.assert_called_with(
                host='localhost',
                port=3307,
                user='root',
                password='secret',
                database='kwtest',
                use_pure=True,
                connection_timeout=3,
                read_timeout=9,
                write_timeout=9,
                get_warnings=True
            )
            assert mock_connect.called, 'mysql.connector.aio.connect should have been called'
        finally:
            await connection.close()


@fact
def mssql_connect_forwards_kwargs_to_driver() -> None:
    mock_connection = MagicMock()
    with patch('mssql_python.connect', MagicMock(return_value=mock_connection)) as mock_connect:
        with connect('mssql://sa:pass@sql.local:1433/kwtest', TrustServerCertificate='yes') as connection:
            conn_str = mock_connect.call_args.args[0]
            kwargs = mock_connect.call_args.kwargs
            assert 'Server=sql.local,1433' in conn_str, f'connection string should target sql.local,1433: {conn_str}'
            assert 'Database=kwtest' in conn_str, f'connection string should target database kwtest: {conn_str}'
            assert 'Provider' not in conn_str, f'connection string should not contain Provider: {conn_str}'
            assert kwargs == {'TrustServerCertificate': 'yes'}, f"(expected={{'TrustServerCertificate': 'yes'}}, actual={kwargs})"


@fact
async def mssql_connect_async_forwards_kwargs_to_driver() -> None:
    mock_connection = MagicMock()
    with patch('mssql_python.connect', MagicMock(return_value=mock_connection)) as mock_connect:
        connection = await connect_async('mssql://sa:pass@sql.local:1433/kwtest', TrustServerCertificate='yes')
        try:
            conn_str = mock_connect.call_args.args[0]
            kwargs = mock_connect.call_args.kwargs
            assert 'Server=sql.local,1433' in conn_str, f'connection string should target sql.local,1433: {conn_str}'
            assert kwargs == {'TrustServerCertificate': 'yes'}, f"(expected={{'TrustServerCertificate': 'yes'}}, actual={kwargs})"
        finally:
            await connection.close()


@fact
def clickhouse_connect_forwards_kwargs_to_driver() -> None:
    mock_connection = MagicMock()
    with patch('clickhouse_connect.dbapi.connection.Connection', MagicMock(return_value=mock_connection)) as mock_connect:
        with connect('clickhouse://default:pass@ch.local:8123/kwtest', query_limit=1000) as connection:
            mock_connect.assert_called_with(
                username='default',
                password='pass',
                host='ch.local',
                database='kwtest',
                port=8123,
                compress=True,
                connect_timeout=3,
                send_receive_timeout=9,
                query_limit=1000
            )
            assert mock_connect.called, 'clickhouse_connect.dbapi.connection.Connection should have been called'


@fact
async def clickhouse_connect_async_forwards_kwargs_to_driver() -> None:
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_get_client = AsyncMock(return_value=mock_client)
    with patch('clickhouse_connect.get_async_client', mock_get_client):
        connection = await connect_async('clickhouse://default:pass@ch.local:8123/kwtest', query_limit=1000)
        try:
            mock_get_client.assert_called_with(
                username='default',
                password='pass',
                host='ch.local',
                port=8123,
                database='kwtest',
                connect_timeout=3,
                send_receive_timeout=9,
                query_limit=1000
            )
            assert mock_get_client.called, 'clickhouse_connect.get_async_client should have been called'
        finally:
            await connection.close()
