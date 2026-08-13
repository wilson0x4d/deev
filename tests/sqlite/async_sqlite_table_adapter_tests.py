# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.sqlite import AsyncSqliteTableAdapter
from deev.utils import connect_async, create_database
from punit import fact, trait
import os
from typing import Any
from uuid import UUID, uuid4


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_basic_crud() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class BasicEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            example: int | None = None
            example_text: str | None = None
            other: UUID | None = None
            floaty: float | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[BasicEntity](connection, create_table=True)

            entity1 = BasicEntity(
                example=456,
                other=uuid4(),
                floaty=3.14
            )
            entity_key = await async_adapter.create(entity1)
            assert entity_key is not None
            assert entity_key.get('id') is not None
            assert entity_key.get('id', 0) > 0

            data = await async_adapter.read(**entity_key)
            assert data is not None
            assert data.example == 456

            data.example_text = 'async_updated'
            await async_adapter.update(data)

            data = await async_adapter.read(**entity_key)
            assert data is not None
            assert data.example_text == 'async_updated'
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_create_kwargs() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class KwargsEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[KwargsEntity](connection, create_table=True)

            key = await async_adapter.create(value='from_kwargs')
            assert key is not None
            assert key.get('id') is not None

            result = await async_adapter.read(**key)
            assert result is not None
            assert result.value == 'from_kwargs'
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_query_and_delete() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class QueryEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            status: str | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[QueryEntity](connection, create_table=True)

            for i in range(3):
                await async_adapter.create(name=f'item_{i}', status='active')

            results = []
            async for row in async_adapter.query(where='status=%?', params=['active']):
                results.append(row)
            assert len(results) >= 3

            matched = results[0]
            assert await async_adapter.exists(**{k: matched.id for k in async_adapter.primary_key}) is True

            await async_adapter.delete(**{k: matched.id for k in async_adapter.primary_key})
            assert await async_adapter.exists(**{k: matched.id for k in async_adapter.primary_key}) is False
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_upsert() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class UpsertEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            count: int | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[UpsertEntity](connection, create_table=True)

            entity1 = UpsertEntity(name='new_entity', count=1)
            pk = await async_adapter.upsert(entity1)
            assert pk is not None
            assert pk.get('id') is not None

            read_back = await async_adapter.read(**pk)
            assert read_back is not None
            assert read_back.name == 'new_entity'

            read_back.count = 2
            await async_adapter.upsert(read_back)
            read_back2 = await async_adapter.read(**pk)
            assert read_back2 is not None
            assert read_back2.count == 2
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_primary_key_property() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class PKEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[PKEntity](connection, create_table=True)
            await async_adapter.create_table()
            assert async_adapter.primary_key == ('id',)
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_uuid_field_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class UuidEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            ref_uuid: UUID | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[UuidEntity](connection, create_table=True)

            target_uuid = uuid4()
            entity1 = UuidEntity(ref_uuid=target_uuid)
            pk = await async_adapter.create(entity1)
            assert pk is not None

            result = await async_adapter.read(**pk)
            assert result is not None
            assert result.ref_uuid == target_uuid
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)


@fact
@trait('sqlite3')
@trait('integration')
async def async_adapter_datetime_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class DateTimeEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            created_at: datetime | None = None

        async with await connect_async(cxnstring) as connection:
            async_adapter = AsyncSqliteTableAdapter[DateTimeEntity](connection, create_table=True)

            now = datetime.now(tz=timezone.utc)
            entity1 = DateTimeEntity(created_at=now)
            pk = await async_adapter.create(entity1)
            assert pk is not None

            result = await async_adapter.read(**pk)
            assert result is not None
            assert result.created_at is not None
            assert abs((result.created_at - now).total_seconds()) < 1
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        if os.path.exists(database_path):
            import shutil
            shutil.rmtree(database_path)
