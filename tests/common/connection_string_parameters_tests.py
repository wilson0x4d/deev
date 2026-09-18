# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common import ConnectionString
from punit import fact, trait


@fact
def oledb_unknown_parameters_in_parameters() -> None:
    cs = ConnectionString(
        "Server=localhost;Database=foo;cluster=default;ENGINE=Replicated('/clickhouse/databases/marketdata', '{shard}', '{replica}');provider=clickhouse"
    )
    parameters = cs.parameters
    assert parameters['server'] == 'localhost'
    assert parameters['database'] == 'foo'
    assert parameters['cluster'] == 'default'
    assert parameters['ENGINE'] == "Replicated('/clickhouse/databases/marketdata', '{shard}', '{replica}')"
    assert parameters['provider'] == 'clickhouse'


@fact
def oledb_all_known_parameters_in_parameters() -> None:
    cs = ConnectionString(
        "Server=127.0.0.1;Database=test;UID=test_usr;PWD=test_pwd;Provider=mysql.connector;Connection Timeout=10;Command Timeout=30"
    )
    parameters = cs.parameters
    assert parameters['server'] == '127.0.0.1'
    assert parameters['database'] == 'test'
    assert parameters['user'] == 'test_usr'
    assert parameters['password'] == 'test_pwd'
    assert parameters['provider'] == 'mysql.connector'
    assert parameters['connect_timeout'] == '10'
    assert parameters['command_timeout'] == '30'


@fact
def oledb_parameters_keys_normalized_to_lowercase() -> None:
    cs = ConnectionString("Data Source=localhost;Catalog=mydb;UID=root;PWD=pass;Provider=mysql")
    parameters = cs.parameters
    assert 'server' in parameters
    assert 'database' in parameters
    assert 'user' in parameters
    assert 'password' in parameters
    assert 'provider' in parameters
    assert parameters['server'] == 'localhost'
    assert parameters['database'] == 'mydb'
    assert parameters['user'] == 'root'
    assert parameters['password'] == 'pass'
    assert parameters['provider'] == 'mysql'


@fact
def oledb_round_trip_unknown_parameters() -> None:
    cs = ConnectionString(
        "Server=localhost;Database=foo;cluster=default;ENGINE=Replicated('/data');provider=clickhouse"
    )
    s = str(cs)
    assert 'cluster=default' in s
    assert "ENGINE=Replicated('/data')" in s


@fact
def dsn_unknown_query_parameters_in_parameters() -> None:
    cs = ConnectionString('mysql://localhost/foo?cluster=default')
    parameters = cs.parameters
    assert parameters['server'] == 'localhost'
    assert parameters['database'] == 'foo'
    assert parameters['cluster'] == 'default'


@fact
def dsn_unknown_query_parameters_in_string() -> None:
    cs = ConnectionString('clickhouse://localhost/foo?cluster=default')
    s = str(cs)
    assert 'cluster=default' in s


@fact
def dsn_round_trip_preserves_query_parameters() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?cluster=prod')
    s = str(cs)
    assert 'cluster=prod' in s
    parameters = cs.parameters
    assert parameters['server'] == 'localhost:3306'
    assert parameters['database'] == 'mydb'
    assert parameters['cluster'] == 'prod'
    # Round-trip through string parses correctly
    cs2 = ConnectionString(s)
    assert cs2.parameters['cluster'] == 'prod'


@fact
def dsn_with_known_query_parameters_in_parameters() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?connect_timeout=10&command_timeout=30')
    parameters = cs.parameters
    assert parameters['connect_timeout'] == '10'
    assert parameters['command_timeout'] == '30'


@fact
def dsn_with_mixed_query_parameters_in_parameters() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?connect_timeout=10&cluster=default')
    parameters = cs.parameters
    assert parameters['connect_timeout'] == '10'
    assert parameters['cluster'] == 'default'


@fact
def new_connection_string_has_empty_known_parameters() -> None:
    cs = ConnectionString()
    parameters = cs.parameters
    assert 'server' not in parameters
    assert 'database' not in parameters
    assert 'user' not in parameters
    assert 'password' not in parameters
    assert 'provider' not in parameters
    assert 'connect_timeout' not in parameters
    assert 'command_timeout' not in parameters


@fact
def parameter_setter_overwrites_known_via_dict() -> None:
    cs = ConnectionString('Server=old;Database=old_db')
    cs.parameters = {'server': 'new_server', 'database': 'new_db'}
    assert cs.server == 'new_server'
    assert cs.database == 'new_db'
    assert cs.parameters['server'] == 'new_server'


@fact
def parameter_setter_overwrites_database_via_dict() -> None:
    cs = ConnectionString('Server=localhost')
    cs.parameters = {'database': 'new_db'}
    assert cs.database == 'new_db'
    assert cs.parameters['database'] == 'new_db'


@fact
def parameter_setter_adds_unknown_via_dict() -> None:
    cs = ConnectionString('Server=localhost')
    cs.parameters = {'custom_param': 'custom_value'}
    parameters = cs.parameters
    assert parameters['custom_param'] == 'custom_value'
    assert parameters['server'] == 'localhost'
    # Unknown parameters also appear in string
    assert 'custom_param=custom_value' in str(cs)


@fact
def dsn_output_format_with_query_parameters() -> None:
    cs = ConnectionString('mysql://root:pass@localhost:3306/mydb?cluster=default')
    parameters = cs.parameters
    assert parameters['server'] == 'localhost:3306'
    assert parameters['database'] == 'mydb'
    assert parameters['cluster'] == 'default'
    s = str(cs)
    assert 'Server=localhost:3306' in s
    assert 'Database=mydb' in s
    assert 'cluster=default' in s


@fact
def empty_dsn_has_empty_known_parameters() -> None:
    cs = ConnectionString()
    assert cs.parameters == {}


@fact
def oledb_only_known_parameters_round_trips() -> None:
    cs = ConnectionString('Server=localhost;Database=mydb')
    s = str(cs)
    cs2 = ConnectionString(s)
    assert cs2.server == 'localhost'
    assert cs2.database == 'mydb'


@fact
def parameter_values_are_strings() -> None:
    cs = ConnectionString()
    cs.server = 'localhost'
    cs.connect_timeout = 10
    parameters = cs.parameters
    assert isinstance(parameters['server'], str)
    assert isinstance(parameters['connect_timeout'], str)
    assert parameters['connect_timeout'] == '10'
