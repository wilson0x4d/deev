# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common import ConnectionString
from punit import fact, inlinedata, theory, trait


@theory
@inlinedata(
    'mysql://root:password@127.0.0.1:3306/mydb',
    '127.0.0.1:3306', 'mydb', 'root', 'password', 'mysql.connector'
)
def parses_mysql_dsn(
    uri: str,
    expected_server: str,
    expected_database: str,
    expected_user: str,
    expected_password: str,
    expected_provider: str
) -> None:
    cs = ConnectionString(uri)
    assert cs.server == expected_server
    assert cs.database == expected_database
    assert cs.user == expected_user
    assert cs.password == expected_password
    assert cs.provider == expected_provider


@theory
@inlinedata(
    'mysql2://appuser:s3cr3t@db.example.com:3307/appdb',
    'db.example.com:3307', 'appdb', 'appuser', 's3cr3t', 'mysql.connector'
)
def parses_mysql2_dsn(
    uri: str,
    expected_server: str,
    expected_database: str,
    expected_user: str,
    expected_password: str,
    expected_provider: str
) -> None:
    cs = ConnectionString(uri)
    assert cs.server == expected_server
    assert cs.database == expected_database
    assert cs.user == expected_user
    assert cs.password == expected_password
    assert cs.provider == expected_provider


@fact
def parses_mysql_without_port() -> None:
    cs = ConnectionString('mysql://root:pass@localhost/mydb')
    assert cs.server == 'localhost'
    assert cs.database == 'mydb'
    assert cs.user == 'root'
    assert cs.password == 'pass'
    assert cs.provider == 'mysql.connector'


@fact
def parses_mysql_without_password() -> None:
    cs = ConnectionString('mysql://user@localhost/mydb')
    assert cs.server == 'localhost'
    assert cs.database == 'mydb'
    assert cs.user == 'user'
    assert cs.password is None
    assert cs.provider == 'mysql.connector'


@theory
@inlinedata(
    'sqlite:///path/to/db.sqlite',
    None, 'path/to/db.sqlite', None, None, 'sqlite'
)
def parses_sqlite_file_dsn(
    uri: str,
    expected_server: str | None,
    expected_database: str | None,
    expected_user: str | None,
    expected_password: str | None,
    expected_provider: str
) -> None:
    cs = ConnectionString(uri)
    assert cs.server == expected_server
    assert cs.database == expected_database
    assert cs.user == expected_user
    assert cs.password == expected_password
    assert cs.provider == expected_provider


@fact
def parses_sqlite_in_memory_dsn() -> None:
    cs = ConnectionString('sqlite:///:memory:')
    assert cs.server is None
    assert cs.database == ':memory:'
    assert cs.user is None
    assert cs.password is None
    assert cs.provider == 'sqlite'


@fact
def parses_sqlite3_dsn() -> None:
    cs = ConnectionString('sqlite3:///data/app.db')
    assert cs.server is None
    assert cs.database == 'data/app.db'
    assert cs.provider == 'sqlite3'


@theory
@inlinedata(
    'mongodb://root:p4ssw0rd@127.0.0.1:27017/mydb',
    '127.0.0.1:27017', 'mydb', 'root', 'p4ssw0rd', 'mongodb'
)
def parses_mongodb_dsn(
    uri: str,
    expected_server: str,
    expected_database: str,
    expected_user: str,
    expected_password: str,
    expected_provider: str
) -> None:
    cs = ConnectionString(uri)
    assert cs.server == expected_server
    assert cs.database == expected_database
    assert cs.user == expected_user
    assert cs.password == expected_password
    assert cs.provider == expected_provider


@theory
@inlinedata(
    'mongodb+srv://admin:secret@cluster0.abc123.mongodb.net/proddb',
    'cluster0.abc123.mongodb.net', 'proddb', 'admin', 'secret', 'mongodb'
)
def parses_mongodb_srv_dsn(
    uri: str,
    expected_server: str,
    expected_database: str,
    expected_user: str,
    expected_password: str,
    expected_provider: str
) -> None:
    cs = ConnectionString(uri)
    assert cs.server == expected_server
    assert cs.database == expected_database
    assert cs.user == expected_user
    assert cs.password == expected_password
    assert cs.provider == expected_provider


@fact
def parses_mongodb_without_password() -> None:
    cs = ConnectionString('mongodb://readonly@mongo.local:27017/readdb')
    assert cs.server == 'mongo.local:27017'
    assert cs.database == 'readdb'
    assert cs.user == 'readonly'
    assert cs.password is None
    assert cs.provider == 'mongodb'


@theory
@inlinedata(
    'clickhouse://default:password@192.168.1.100:8123/analytics',
    '192.168.1.100:8123', 'analytics', 'default', 'password', 'clickhouse'
)
@trait('clickhouse')
def parses_clickhouse_dsn(
    uri: str,
    expected_server: str,
    expected_database: str,
    expected_user: str,
    expected_password: str,
    expected_provider: str
) -> None:
    cs = ConnectionString(uri)
    assert cs.server == expected_server
    assert cs.database == expected_database
    assert cs.user == expected_user
    assert cs.password == expected_password
    assert cs.provider == expected_provider


@fact
@trait('clickhouse')
def parses_clickhouse_without_password() -> None:
    cs = ConnectionString('clickhouse://readonly@ch.example.com/metrics')
    assert cs.server == 'ch.example.com'
    assert cs.database == 'metrics'
    assert cs.user == 'readonly'
    assert cs.password is None
    assert cs.provider == 'clickhouse'


@fact
@trait('clickhouse')
def parses_clickhouse_default_port() -> None:
    cs = ConnectionString('clickhouse://admin:pass@localhost/testdb')
    assert cs.server == 'localhost'
    assert cs.database == 'testdb'
    assert cs.provider == 'clickhouse'


@fact
def parses_dsn_with_connect_timeout() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?connect_timeout=10')
    assert cs.connect_timeout == 10
    assert cs.user == 'user'
    assert cs.password == 'pass'
    assert cs.server == 'localhost:3306'
    assert cs.database == 'mydb'


@fact
@trait('clickhouse')
def parses_dsn_with_command_timeout() -> None:
    cs = ConnectionString('clickhouse://default:@ch.local:8123/db?command_timeout=30')
    assert cs.command_timeout == 30
    assert cs.user == 'default'
    assert cs.password == ''
    assert cs.server == 'ch.local:8123'
    assert cs.database == 'db'


@fact
def parses_dsn_with_both_timeouts() -> None:
    cs = ConnectionString('mongodb://appuser:secret@mongo:27017/appdb?connect_timeout=5&command_timeout=15')
    assert cs.connect_timeout == 5
    assert cs.command_timeout == 15
    assert cs.user == 'appuser'
    assert cs.password == 'secret'
    assert cs.server == 'mongo:27017'
    assert cs.database == 'appdb'


@fact
def parses_mysql_with_percent_encoded_credentials() -> None:
    cs = ConnectionString('mysql://user%40domain:p%40ss%3Aword@localhost/db')
    assert cs.user == 'user@domain'
    assert cs.password == 'p@ss:word'
    assert cs.server == 'localhost'
    assert cs.database == 'db'
    assert cs.provider == 'mysql.connector'


@fact
def parses_dbprop_semicolon_string_with_no_scheme() -> None:
    cs = ConnectionString('Server=localhost;Database=test;UID=user;PWD=pass;Provider=mysql.connector')
    assert cs.server == 'localhost'
    assert cs.database == 'test'
    assert cs.user == 'user'
    assert cs.password == 'pass'
    assert cs.provider == 'mysql.connector'


@fact
def parses_empty_string_does_not_crash() -> None:
    cs = ConnectionString('')
    assert cs.provider is None
    assert cs.database is None
    assert cs.user is None
    assert cs.password is None
    assert cs.server is None


@fact
def handles_dsn_with_no_database() -> None:
    cs = ConnectionString('mysql://user:pass@localhost')
    assert cs.server == 'localhost'
    assert cs.database is None
    assert cs.user == 'user'
    assert cs.password == 'pass'
    assert cs.provider == 'mysql.connector'


@fact
def handles_mongodb_with_no_database() -> None:
    cs = ConnectionString('mongodb://user:pass@mongo.local:27017')
    assert cs.server == 'mongo.local:27017'
    assert cs.database is None
    assert cs.provider == 'mongodb'


@fact
def constructs_dsn_like_output_for_mysql() -> None:
    cs = ConnectionString('mysql://root:pass@localhost:3306/mydb')
    assert 'Provider=mysql.connector' in str(cs)
    assert 'Server=localhost:3306' in str(cs)
    assert 'Database=mydb' in str(cs)
    assert 'UID=root' in str(cs)
    assert 'PWD=pass' in str(cs)
