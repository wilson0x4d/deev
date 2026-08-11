# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs, urlparse, unquote


_DSN_TO_PROVIDER: dict[str, str] = {
    'mysql': 'mysql.connector',
    'mysql2': 'mysql.connector',
    'sqlite': 'sqlite',
    'sqlite3': 'sqlite3',
    'mongodb': 'mongodb',
    'mongodb+srv': 'mongodb',
    'clickhouse': 'clickhouse',
}


class ConnectionString:
    """
    A type-safe connection string representation that can parse and build constituent parts.

    Supports two input formats:

    **DSN (URI) format**

    Standard URI connection strings, automatically mapped to the appropriate provider:

    ================    ===========================================
    DSN Scheme          Mapped Provider
    ================    ===========================================
    ``mysql``           ``mysql.connector``
    ``mysql2``          ``mysql.connector``
    ``sqlite``          ``sqlite``
    ``sqlite3``         ``sqlite3``
    ``mongodb``         ``mongodb``
    ``mongodb+srv``     ``mongodb``
    ``clickhouse``      ``clickhouse``
    ================    ===========================================

    Examples:

    .. code-block:: python

        # MySQL
        ConnectionString('mysql://root:pass@127.0.0.1:3306/mydb')

        # SQLite file
        ConnectionString('sqlite3:///path/to/db.sqlite')

        # SQLite in-memory
        ConnectionString('sqlite:///:memory:')

        # MongoDB
        ConnectionString('mongodb://user:pass@mongo.local:27017/mydb')

        # MongoDB Atlas / SRV
        ConnectionString('mongodb+srv://admin:secret@cluster.mongodb.net/proddb')

        # ClickHouse
        ConnectionString('clickhouse://default:pass@ch.local:8123/analytics')

    DSN query parameters ``connect_timeout`` and ``command_timeout`` are supported, e.g.:

    .. code-block:: python

        ConnectionString('mysql://user:pass@localhost:3306/db?connect_timeout=10&command_timeout=30')

    Credentials may be percent-encoded as in standard URIs (``urlparse`` decodes them automatically).

    **OLEDB / key-value format**

    Semicolon-delimited ``Key=Value`` pairs, as used in ADO / ADO.NET connection strings:

    .. code-block:: python

        ConnectionString('Server=127.0.0.1;Database=mydb;UID=root;PWD=pass;Provider=mysql.connector')

    Recognized keys (case-insensitive):

    ======================  ===================================
    Key                     Maps To
    ======================  ===================================
    ``server``              ``server``
    ``database``            ``database``
    ``uid``                 ``user``
    ``user``                ``user``
    ``user id``             ``user``
    ``username``            ``user``
    ``pwd``                 ``password``
    ``password``            ``password``
    ``pass``                ``password``
    ``provider``            ``provider``
    ``connection timeout``  ``connect_timeout``
    ``command timeout``     ``command_timeout``
    ======================  ===================================

    **Properties**

    All fields are accessible via getter/setter properties:
    ``server``, ``database``, ``user``, ``password``, ``provider``,
    ``connect_timeout``, ``command_timeout``.

    ``str(connectionString)`` reconstructs the OLEDB-style format from the parsed parts.
    """

    __server: Optional[str]
    __database: Optional[str]
    __user: Optional[str]
    __password: Optional[str]
    __provider: Optional[str]
    __connect_timeout: Optional[int]
    __command_timeout: Optional[int]

    def __init__(
        self,
        connection_str: Optional[str] = None
    ):
        self.__server = None
        self.__database = None
        self.__user = None
        self.__password = None
        self.__provider = None
        self.__connect_timeout = None
        self.__command_timeout = None
        if connection_str is not None:
            self.parse(connection_str)

    def __str__(self) -> str:
        parts = []
        if self.server is not None:
            parts.append(f'Server={self.server}')
        if self.database is not None:
            parts.append(f'Database={self.database}')
        if self.user is not None:
            parts.append(f'UID={self.user}')
        if self.password is not None:
            parts.append(f'PWD={self.password}')
        if self.provider is not None:
            parts.append(f'Provider={self.provider}')
        if self.connect_timeout is not None:
            parts.append(f'Connection Timeout={self.connect_timeout}')
        if self.command_timeout is not None:
            parts.append(f'Command Timeout={self.command_timeout}')
        return ';'.join(parts)

    @property
    def server(self) -> Optional[str]:
        return self.__server

    @server.setter
    def server(self, value: Optional[str]):
        self.__server = value

    @property
    def database(self) -> Optional[str]:
        return self.__database

    @database.setter
    def database(self, value: Optional[str]):
        self.__database = value

    @property
    def user(self) -> Optional[str]:
        return self.__user

    @user.setter
    def user(self, value: Optional[str]):
        self.__user = value

    @property
    def password(self) -> Optional[str]:
        return self.__password

    @password.setter
    def password(self, value: Optional[str]):
        self.__password = value

    @property
    def provider(self) -> Optional[str]:
        return self.__provider

    @provider.setter
    def provider(self, value: Optional[str]):
        self.__provider = value

    @property
    def connect_timeout(self) -> Optional[int]:
        return self.__connect_timeout

    @connect_timeout.setter
    def connect_timeout(self, value: Optional[int]):
        self.__connect_timeout = value

    @property
    def command_timeout(self) -> Optional[int]:
        return self.__command_timeout

    @command_timeout.setter
    def command_timeout(self, value: Optional[int]):
        self.__command_timeout = value

    def parse(self, connectionstring: Optional[str]) -> ConnectionString:
        if not connectionstring:
            return self
        parsed = urlparse(connectionstring)
        if parsed.scheme and parsed.scheme in _DSN_TO_PROVIDER:
            self.__parse_dsn(parsed)
        else:
            self.__parse_oledb(connectionstring)
        return self

    def __parse_dsn(self, parsed) -> None:
        provider = _DSN_TO_PROVIDER[parsed.scheme]
        self.provider = provider
        if parsed.username is not None:
            self.user = unquote(parsed.username)
        if parsed.password is not None:
            self.password = unquote(parsed.password)
        host_port = parsed.hostname or ''
        if parsed.port:
            host_port = f'{host_port}:{parsed.port}'
        self.server = host_port or None
        if parsed.path:
            db = parsed.path.lstrip('/')
            self.database = db or None
        params = parse_qs(parsed.query)
        if 'connect_timeout' in params:
            self.connect_timeout = int(params['connect_timeout'][0])
        if 'command_timeout' in params:
            self.command_timeout = int(params['command_timeout'][0])

    def __parse_oledb(self, connectionstring: str) -> None:
        parts = connectionstring.split(';')
        for part in parts:
            if not part:
                continue
            key, value = part.split('=')
            match key.lower():
                case 'server' | 'data source':
                    self.server = value
                case 'database' | 'catalog':
                    self.database = value
                case 'uid' | 'user' | 'user id' | 'username':
                    self.user = value
                case 'pwd' | 'password' | 'pass':
                    self.password = value
                case 'provider':
                    self.provider = value
                case 'connection timeout':
                    self.connect_timeout = int(value)
                case 'command timeout':
                    self.command_timeout = int(value)


__all__ = ['ConnectionString']
