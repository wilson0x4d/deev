# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import urllib.parse


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

    __server: str | None
    __database: str | None
    __user: str | None
    __password: str | None
    __provider: str | None
    __connect_timeout: int | None
    __command_timeout: int | None
    __parameters: dict[str, str]

    def __init__(
        self,
        connection_str: str | None = None
    ):
        self.__server = None
        self.__database = None
        self.__user = None
        self.__password = None
        self.__provider = None
        self.__connect_timeout = None
        self.__command_timeout = None
        self.__parameters = {}
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
        for key, value in self.__parameters.items():
            parts.append(f'{key}={value}')
        return ';'.join(parts)

    @property
    def server(self) -> str | None:
        return self.__server

    @server.setter
    def server(self, value: str | None):
        self.__server = value

    @property
    def database(self) -> str | None:
        return self.__database

    @database.setter
    def database(self, value: str | None):
        self.__database = value

    @property
    def user(self) -> str | None:
        return self.__user

    @user.setter
    def user(self, value: str | None):
        self.__user = value

    @property
    def password(self) -> str | None:
        return self.__password

    @password.setter
    def password(self, value: str | None):
        self.__password = value

    @property
    def provider(self) -> str | None:
        return self.__provider

    @provider.setter
    def provider(self, value: str | None):
        self.__provider = value

    @property
    def connect_timeout(self) -> int | None:
        return self.__connect_timeout

    @connect_timeout.setter
    def connect_timeout(self, value: int | None):
        self.__connect_timeout = value

    @property
    def command_timeout(self) -> int | None:
        return self.__command_timeout

    @command_timeout.setter
    def command_timeout(self, value: int | None):
        self.__command_timeout = value

    def to_parameters(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.__server is not None:
            params['server'] = str(self.__server)
        if self.__database is not None:
            params['database'] = str(self.__database)
        if self.__user is not None:
            params['user'] = str(self.__user)
        if self.__password is not None:
            params['password'] = str(self.__password)
        if self.__provider is not None:
            params['provider'] = str(self.__provider)
        if self.__connect_timeout is not None:
            params['connect_timeout'] = str(self.__connect_timeout)
        if self.__command_timeout is not None:
            params['command_timeout'] = str(self.__command_timeout)
        params.update(self.__parameters)
        return params

    @property
    def parameters(self) -> dict[str, str]:
        return self.to_parameters()

    @parameters.setter
    def parameters(self, value: dict[str, str]) -> None:
        for key, val in value.items():
            key_lower = key.lower()
            match key_lower:
                case 'server' | 'data source':
                    self.__server = val
                case 'database' | 'catalog':
                    self.__database = val
                case 'uid' | 'user' | 'user id' | 'username':
                    self.__user = val
                case 'pwd' | 'password' | 'pass':
                    self.__password = val
                case 'provider':
                    self.__provider = val
                case 'connect_timeout':
                    self.__connect_timeout = int(val)
                case 'command_timeout':
                    self.__command_timeout = int(val)
                case _:
                    self.__parameters[key_lower] = val

    def parse(self, connectionstring: str | None) -> ConnectionString:
        if not connectionstring:
            return self
        parsed: urllib.parse.ParseResult = urllib.parse.urlparse(connectionstring)
        if parsed.scheme and parsed.scheme in _DSN_TO_PROVIDER:
            self.__parse_dsn(parsed)
        else:
            self.__parse_oledb(connectionstring)
        return self

    def __parse_dsn(self, parsed: urllib.parse.ParseResult) -> None:
        provider = _DSN_TO_PROVIDER[parsed.scheme]
        self.provider = provider
        if parsed.username is not None:
            self.user = urllib.parse.unquote(parsed.username)
        if parsed.password is not None:
            self.password = urllib.parse.unquote(parsed.password)
        host_port = parsed.hostname or ''
        if parsed.port:
            host_port = f'{host_port}:{parsed.port}'
        self.server = host_port or None
        if parsed.path:
            db = parsed.path.lstrip('/')
            self.database = db or None
        for key, values in urllib.parse.parse_qs(parsed.query).items():
            if key == 'connect_timeout':
                self.connect_timeout = int(values[0])
            elif key == 'command_timeout':
                self.command_timeout = int(values[0])
            else:
                self.__parameters[key] = values[0]

    def __parse_oledb(self, connectionstring: str) -> None:
        parts = connectionstring.split(';')
        for part in parts:
            if not part:
                continue
            key, value = part.split('=', 1)
            key_lower = key.lower()
            match key_lower:
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
                case _:
                    self.__parameters[key_lower] = value


__all__ = ['ConnectionString']
