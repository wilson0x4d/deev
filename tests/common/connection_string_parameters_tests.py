# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common import ConnectionString
from punit import fact, trait


@fact
def oledb_unknown_params_in_parameters() -> None:
    cs = ConnectionString(
        "Server=localhost;Database=foo;cluster=default;ENGINE=Replicated('/clickhouse/databases/marketdata', '{shard}', '{replica}');provider=clickhouse"
    )
    params = cs.parameters
    assert params['server'] == 'localhost'
    assert params['database'] == 'foo'
    assert params['cluster'] == 'default'
    assert params['engine'] == "Replicated('/clickhouse/databases/marketdata', '{shard}', '{replica}')"
    assert params['provider'] == 'clickhouse'


@fact
def oledb_all_known_params_in_parameters() -> None:
    cs = ConnectionString(
        "Server=127.0.0.1;Database=test;UID=test_usr;PWD=test_pwd;Provider=mysql.connector;Connection Timeout=10;Command Timeout=30"
    )
    params = cs.parameters
    assert params['server'] == '127.0.0.1'
    assert params['database'] == 'test'
    assert params['user'] == 'test_usr'
    assert params['password'] == 'test_pwd'
    assert params['provider'] == 'mysql.connector'
    assert params['connect_timeout'] == '10'
    assert params['command_timeout'] == '30'


@fact
def oledb_parameters_keys_normalized_to_lowercase() -> None:
    cs = ConnectionString("Data Source=localhost;Catalog=mydb;UID=root;PWD=pass;Provider=mysql")
    params = cs.parameters
    assert 'server' in params
    assert 'database' in params
    assert 'user' in params
    assert 'password' in params
    assert 'provider' in params
    assert params['server'] == 'localhost'
    assert params['database'] == 'mydb'
    assert params['user'] == 'root'
    assert params['password'] == 'pass'
    assert params['provider'] == 'mysql'


@fact
def oledb_round_trip_unknown_params() -> None:
    cs = ConnectionString(
        "Server=localhost;Database=foo;cluster=default;ENGINE=Replicated('/data');provider=clickhouse"
    )
    s = str(cs)
    assert 'cluster=default' in s
    assert "engine=Replicated('/data')" in s


@fact
def dsn_unknown_query_params_in_parameters() -> None:
    cs = ConnectionString('mysql://localhost/foo?cluster=default')
    params = cs.parameters
    assert params['server'] == 'localhost'
    assert params['database'] == 'foo'
    assert params['cluster'] == 'default'


@fact
def dsn_unknown_query_params_in_string() -> None:
    cs = ConnectionString('clickhouse://localhost/foo?cluster=default')
    s = str(cs)
    assert 'cluster=default' in s


@fact
def dsn_round_trip_preserves_query_params() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?cluster=prod')
    s = str(cs)
    assert 'cluster=prod' in s
    params = cs.parameters
    assert params['server'] == 'localhost:3306'
    assert params['database'] == 'mydb'
    assert params['cluster'] == 'prod'
    # Round-trip through string parses correctly
    cs2 = ConnectionString(s)
    assert cs2.parameters['cluster'] == 'prod'


@fact
def dsn_with_known_query_params_in_parameters() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?connect_timeout=10&command_timeout=30')
    params = cs.parameters
    assert params['connect_timeout'] == '10'
    assert params['command_timeout'] == '30'


@fact
def dsn_with_mixed_query_params_in_parameters() -> None:
    cs = ConnectionString('mysql://user:pass@localhost:3306/mydb?connect_timeout=10&cluster=default')
    params = cs.parameters
    assert params['connect_timeout'] == '10'
    assert params['cluster'] == 'default'


@fact
def new_connection_string_has_empty_known_params() -> None:
    cs = ConnectionString()
    params = cs.parameters
    assert 'server' not in params
    assert 'database' not in params
    assert 'user' not in params
    assert 'password' not in params
    assert 'provider' not in params
    assert 'connect_timeout' not in params
    assert 'command_timeout' not in params


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
    params = cs.parameters
    assert params['custom_param'] == 'custom_value'
    assert params['server'] == 'localhost'
    # Unknown params also appear in string
    assert 'custom_param=custom_value' in str(cs)


@fact
def dsn_output_format_with_query_params() -> None:
    cs = ConnectionString('mysql://root:pass@localhost:3306/mydb?cluster=default')
    params = cs.parameters
    assert params['server'] == 'localhost:3306'
    assert params['database'] == 'mydb'
    assert params['cluster'] == 'default'
    s = str(cs)
    assert 'Server=localhost:3306' in s
    assert 'Database=mydb' in s
    assert 'cluster=default' in s


@fact
def empty_dsn_has_empty_known_params() -> None:
    cs = ConnectionString()
    assert cs.parameters == {}


@fact
def oledb_only_known_params_round_trips() -> None:
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
    params = cs.parameters
    assert isinstance(params['server'], str)
    assert isinstance(params['connect_timeout'], str)
    assert params['connect_timeout'] == '10'
