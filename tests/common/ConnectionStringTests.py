# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common import ConnectionString
from punit import fact, inlinedata, theory
from typing import Optional


@theory
@inlinedata('127.0.0.1', 'test', 'test_usr', 'test_pwd', 'mysql.connector', 'Server=127.0.0.1;Database=test;UID=test_usr;PWD=test_pwd;Provider=mysql.connector')
def constructs_deterministic_strings(
    server: str,
    database: str,
    user: str,
    password: str,
    provider: str,
    expected: str
) -> None:
    connectionstring = ConnectionString()
    connectionstring.server = server
    connectionstring.database = database
    connectionstring.user = user
    connectionstring.password = password
    connectionstring.provider = provider
    assert str(connectionstring) == expected, f'{connectionstring} != {expected}'

@fact
def supports_assignments() -> None:
    connectionstring = ConnectionString()
    connectionstring.server = 'foo'
    connectionstring.database = 'bar'
    connectionstring.user = 'baz'
    connectionstring.password = 'blah'
    connectionstring.provider = 'bleh'
    assert str(connectionstring) == 'Server=foo;Database=bar;UID=baz;PWD=blah;Provider=bleh'

@theory
@inlinedata('Server=127.0.0.1;Database=test;UID=test_usr;PWD=test_pwd;Provider=mysql.connector', '127.0.0.1', 'test', 'test_usr', 'test_pwd', 'mysql.connector')
def supports_parse(connection_str: str, server: Optional[str], database: Optional[str], user: Optional[str], password: Optional[str], provider: Optional[str]) -> None:
    connectionstring = ConnectionString(connection_str)
    assert connectionstring.server == server
    assert connectionstring.database == database
    assert connectionstring.user == user
    assert connectionstring.password == password
    assert connectionstring.provider == provider
