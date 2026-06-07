# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.mongodb.MongoProxyCursor import MongoProxyCursor
from deev.utils import connect
from punit import fact, trait


def get_mongodb_connectionstring():
    """Get the ConnectionString to be used by mongodb tests."""
    import appsettings2
    from deev.common.ConnectionString import ConnectionString
    configuration = appsettings2.get_configuration()
    connection_str = configuration.connections.mongodb_test
    return ConnectionString(connection_str)


@fact
@trait('integration')
@trait('mongodb')
def connection_cursor_returns_proxy() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        cursor = connection.cursor()
        assert isinstance(cursor, MongoProxyCursor), 'cursor should be a MongoProxyCursor'


@fact
@trait('integration')
@trait('mongodb')
def connection_commit_does_not_raise() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        connection.commit()
        connection.rollback()


@fact
@trait('integration')
@trait('mongodb')
def connection_context_manager_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        assert connection is not None


@fact
@trait('integration')
@trait('mongodb')
def connection_mongo_connection_property_exists() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        mongo_conn = getattr(connection, 'mongo_connection', None)
        assert mongo_conn is not None, 'mongo_connection property should exist'
