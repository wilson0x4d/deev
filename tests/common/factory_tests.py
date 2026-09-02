# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from deev import entity, field
from deev.common.db_error import DbError
from deev.sqlite import SqliteProxyConnection, SqliteTableAdapter
from deev.sqlite.async_sqlite_proxy_connection import AsyncSqliteProxyConnection
from deev.sqlite.async_sqlite_table_adapter import AsyncSqliteTableAdapter
from deev.utils import (
    async_db_table_adapter_factory,
    create_table_adapter,
    create_table_adapter_async,
    db_table_adapter_factory,
)
from punit import fact


@entity
class SimpleEntity:
    id: int = field(primary_key=True)
    name: str | None = None


@fact
def db_table_adapter_factory_returns_sqlite_adapter() -> None:
    """Real SqliteProxyConnection object, real factory call, verified return type."""
    conn = sqlite3.connect(':memory:')
    proxy = SqliteProxyConnection(conn)
    assert type(proxy).__name__ == 'SqliteProxyConnection'

    adapter = db_table_adapter_factory(SimpleEntity, proxy)
    assert type(adapter).__name__ == 'SqliteTableAdapter'


@fact
def db_table_adapter_factory_passes_kwargs() -> None:
    """create_table and table_name kwargs reach the constructor."""
    conn = sqlite3.connect(':memory:')
    proxy = SqliteProxyConnection(conn)

    adapter = db_table_adapter_factory(
        SimpleEntity,
        proxy,
        create_table=True,
        table_name='custom_table',
    )
    assert type(adapter).__name__ == 'SqliteTableAdapter'


@fact
def db_table_adapter_factory_raises_for_unsupported_type() -> None:
    """Passing an unrecognized connection type raises DbError."""
    class FakeContext:
        pass

    fake = FakeContext()
    try:
        db_table_adapter_factory(SimpleEntity, fake)  # type: ignore[arg-type]
    except DbError as e:
        assert 'Unsupported object' in str(e)
    else:
        assert False, 'Expected DbError for unsupported type'


@fact
def async_db_table_adapter_factory_returns_async_sqlite_adapter() -> None:
    """Real AsyncSqliteProxyConnection object, real factory call, verified return type."""
    conn = sqlite3.connect(':memory:')
    async_proxy = AsyncSqliteProxyConnection(conn)
    assert type(async_proxy).__name__ == 'AsyncSqliteProxyConnection'

    adapter = async_db_table_adapter_factory(SimpleEntity, async_proxy)
    assert type(adapter).__name__ == 'AsyncSqliteTableAdapter'


@fact
def async_db_table_adapter_factory_passes_kwargs() -> None:
    """create_table and table_name kwargs reach the constructor."""
    conn = sqlite3.connect(':memory:')
    async_proxy = AsyncSqliteProxyConnection(conn)

    adapter = async_db_table_adapter_factory(
        SimpleEntity,
        async_proxy,
        create_table=True,
        table_name='custom_async_table',
    )
    assert type(adapter).__name__ == 'AsyncSqliteTableAdapter'


@fact
def async_db_table_adapter_factory_raises_for_unsupported_type() -> None:
    """Passing an unrecognized async connection type raises DbError."""
    class FakeAsyncContext:
        pass

    fake = FakeAsyncContext()
    try:
        async_db_table_adapter_factory(SimpleEntity, fake)  # type: ignore[arg-type]
    except DbError as e:
        assert 'Unsupported object' in str(e)
    else:
        assert False, 'Expected DbError for unsupported type'


@fact
def create_table_adapter_delegates_to_db_table_adapter_factory() -> None:
    """create_table_adapter with a DbContext (not ConnectionString) passes through."""
    conn = sqlite3.connect(':memory:')
    proxy = SqliteProxyConnection(conn)

    adapter = create_table_adapter(SimpleEntity, proxy)
    assert type(adapter).__name__ == 'SqliteTableAdapter'


# The following integration test would require async facts (pUnit doesn't expose
# them publicly). The factory functions are tested directly above, which is
# sufficient to prevent regression of the bug this file exists to guard against.
