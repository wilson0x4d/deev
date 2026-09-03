# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import (
    connect,
    create_database,
    connect_async,
    create_table_adapter_async,
)
from deev.mysql.async_mysql_table_adapter import AsyncMysqlTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait


def get_mysql_connectionstring() -> ConnectionString:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    return cxnstring


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_basic_crud() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
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
            adapter = AsyncMysqlTableAdapter[BasicEntity](connection, create_table=True)

            entity1 = BasicEntity(
                example=789,
                other=uuid4(),
                floaty=2.71
            )
            entity_key = await adapter.create(entity1)
            assert entity_key is not None
            assert entity_key.get('id') is not None
            assert entity_key.get('id', 0) > 0

            data = await adapter.read(**entity_key)
            assert data is not None
            assert data.example == 789

            data.example_text = 'async_updated'
            await adapter.update(data)

            data = await adapter.read(**entity_key)
            assert data is not None
            assert data.example_text == 'async_updated'
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_create_kwargs() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        @entity
        class KwargsEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncMysqlTableAdapter[KwargsEntity](connection, create_table=True)

            key = await adapter.create(value='from_kwargs')
            assert key is not None
            assert key.get('id') is not None

            result = await adapter.read(**key)
            assert result is not None
            assert result.value == 'from_kwargs'
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_query_and_delete() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        @entity
        class QueryEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            status: str | None = None

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncMysqlTableAdapter[QueryEntity](connection, create_table=True)

            for i in range(3):
                await adapter.create(name=f'item_{i}', status='active')

            results = []
            async for row in adapter.query(where='status=%?', params=['active']):
                results.append(row)
            assert len(results) >= 3

            matched = results[0]
            pk_values = {k: getattr(matched, k, None) for k in adapter.primary_key}
            assert await adapter.exists(**pk_values) is True

            await adapter.delete(**pk_values)
            assert await adapter.exists(**pk_values) is False
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_upsert() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        @entity
        class UpsertEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            count: int | None = None

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncMysqlTableAdapter[UpsertEntity](connection, create_table=True)

            entity1 = UpsertEntity(name='new_entity', count=1)
            pk = await adapter.upsert(entity1)
            assert pk is not None
            assert pk.get('id') is not None

            read_back = await adapter.read(**pk)
            assert read_back is not None
            assert read_back.name == 'new_entity'

            read_back.count = 3
            await adapter.upsert(read_back)
            read_back2 = await adapter.read(**pk)
            assert read_back2 is not None
            assert read_back2.count == 3
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_primary_key_property() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        @entity
        class PKEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncMysqlTableAdapter[PKEntity](connection, create_table=True)
            assert adapter.primary_key == ('id',)
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_uuid_field_roundtrip() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        @entity
        class UuidEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            ref_uuid: UUID | None = None

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncMysqlTableAdapter[UuidEntity](connection, create_table=True)

            target_uuid = uuid4()
            entity1 = UuidEntity(ref_uuid=target_uuid)
            pk = await adapter.create(entity1)
            assert pk is not None

            result = await adapter.read(**pk)
            assert result is not None
            assert result.ref_uuid == target_uuid
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass


@fact
@trait('mysql')
@trait('integration')
async def async_adapter_datetime_roundtrip() -> None:
    cxnstring = get_mysql_connectionstring()
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    try:
        @entity
        class DateTimeEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            created_at: datetime | None = None

        async with await connect_async(cxnstring) as connection:
            adapter = AsyncMysqlTableAdapter[DateTimeEntity](connection, create_table=True)

            now = datetime.now(tz=timezone.utc)
            entity1 = DateTimeEntity(created_at=now)
            pk = await adapter.create(entity1)
            assert pk is not None

            result = await adapter.read(**pk)
            assert result is not None
            assert result.created_at is not None
            assert abs((result.created_at - now).total_seconds()) < 1
    finally:
        try:
            def _drop_db() -> None:
                with connect(cxnstring) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DROP DATABASE `{cxnstring.database}`;')
                    cursor.close()
                    conn.commit()
                    conn.close()
            _drop_db()
        except Exception:
            pass
