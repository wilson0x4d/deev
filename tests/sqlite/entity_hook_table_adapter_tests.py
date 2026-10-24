# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev import entity, field
from deev.common import ConnectionString
from deev.sqlite import AsyncSQLiteTableAdapter, SQLiteTableAdapter
from deev.utils import connect, connect_async, create_database
from punit import fact, trait
import os
import shutil
from uuid import uuid4


@fact
@trait('sqlite')
@trait('integration')
def hook_fires_on_new_table() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_hook_users')
        class HookUser:
            id: int = field(autoincrement=True, primary_key=True, default=None)
            name: str = field(default='')

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(table_adapter.__class__.__name__)
                table_adapter.create(name='seeded')

        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[HookUser](connection)
            adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'SQLiteTableAdapter', f"(expected='SQLiteTableAdapter', actual={calls[0]})"
            # the hook's seed data is visible after create_table returns
            row = adapter.read(id=1)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded', f"(expected='seeded', actual={row.name})"
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            shutil.rmtree(database_path)


@fact
@trait('sqlite')
@trait('integration')
def hook_does_not_refire_on_second_create_table() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_hook_norefire')
        class NoRefireUser:
            id: int = field(autoincrement=True, primary_key=True, default=None)
            name: str = field(default='')

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(1)

        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[NoRefireUser](connection)
            adapter.create_table()
            adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            shutil.rmtree(database_path)


@fact
@trait('sqlite')
@trait('integration')
def hook_does_not_fire_when_table_already_exists() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_hook_preexisting')
        class PreExistingUser:
            id: int = field(autoincrement=True, primary_key=True, default=None)
            name: str = field(default='')

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(1)

        with connect(cxnstring) as connection:
            # create the table out-of-band so create_table() sees it as pre-existing
            cursor = connection.cursor()
            cursor.execute('CREATE TABLE [tbl_hook_preexisting] ([id] INTEGER PRIMARY KEY AUTOINCREMENT, [name] TEXT NOT NULL)')

            adapter = SQLiteTableAdapter[PreExistingUser](connection)
            adapter.create_table()

            assert len(calls) == 0, f"(expected=0, actual={len(calls)})"
            # and no DDL was re-executed: a second create_table is a no-op
            adapter.create_table()
            assert len(calls) == 0, f"(expected=0, actual={len(calls)})"
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            shutil.rmtree(database_path)


@fact
@trait('sqlite')
@trait('integration')
def create_table_flag_fires_hook_lazily() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_hook_lazy')
        class LazyUser:
            id: int = field(autoincrement=True, primary_key=True, default=None)
            name: str = field(default='')

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(1)
                table_adapter.create(name='seeded-lazy')

        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[LazyUser](connection, create_table=True)
            # first operation triggers deferred init which creates the table
            row = adapter.read(id=1)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded-lazy', f"(expected='seeded-lazy', actual={row.name})"
            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            shutil.rmtree(database_path)


@fact
@trait('sqlite')
@trait('integration')
async def async_adapter_awaits_async_hook() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_hook_async_users')
        class AsyncHookUser:
            id: int = field(autoincrement=True, primary_key=True, default=None)
            name: str = field(default='')

            @staticmethod
            async def on_create_table(table_adapter) -> None:
                import inspect
                calls.append(table_adapter.__class__.__name__)
                result = table_adapter.create(name='seeded-async')
                if inspect.iscoroutine(result):
                    await result

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncSQLiteTableAdapter[AsyncHookUser](connection)
            await adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'AsyncSQLiteTableAdapter', f"(expected='AsyncSQLiteTableAdapter', actual={calls[0]})"
            row = await adapter.read(id=1)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded-async', f"(expected='seeded-async', actual={row.name})"

            # a second create_table must not re-fire the hook
            await adapter.create_table()
            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            shutil.rmtree(database_path)


@fact
@trait('sqlite')
@trait('integration')
async def async_adapter_works_with_sync_hook() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_hook_async_syncfn')
        class SyncFnUser:
            id: int = field(autoincrement=True, primary_key=True, default=None)
            name: str = field(default='')

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(table_adapter.__class__.__name__)

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncSQLiteTableAdapter[SyncFnUser](connection)
            await adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'AsyncSQLiteTableAdapter', f"(expected='AsyncSQLiteTableAdapter', actual={calls[0]})"
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            shutil.rmtree(database_path)
