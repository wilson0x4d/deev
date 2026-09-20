# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import (
    connect,
    connect_async,
    create_table_adapter_async,
)
from deev.mssql.async_mssql_table_adapter import AsyncMSSQLTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait


def get_mssql_connectionstring() -> ConnectionString:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    return cxnstring


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_basic_crud() -> None:
    cxnstring = get_mssql_connectionstring()
    unique_text = uuid4().hex[:6]
    async with await connect_async(cxnstring) as connection:
        @entity(table_name='tbl_AABC')
        class BasicEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            example: int | None = None
            example_text: str | None = None
            other: UUID | None = None
            floaty: float | None = None

        adapter = AsyncMSSQLTableAdapter[BasicEntity](connection, create_table=True)

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

        data.example_text = unique_text
        await adapter.update(data)

        data = await adapter.read(**entity_key)
        assert data is not None
        assert data.example_text == unique_text


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_create_kwargs() -> None:
    cxnstring = get_mssql_connectionstring()
    @entity
    class KwargsEntity:
        id: int = field(autoincrement=True, primary_key=True, default=0)
        value: str | None = None

    async with await connect_async(cxnstring) as connection:
        adapter = AsyncMSSQLTableAdapter[KwargsEntity](connection, create_table=True)

        value = uuid4().hex[1:7]
        key = await adapter.create(value=value)
        assert key is not None
        assert key.get('id') is not None

        result = await adapter.read(**key)
        assert result is not None
        assert result.value == value


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_query_and_delete() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        @entity(table_name='tbl_ms_aaqad')
        class QueryEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            status: str | None = None

        adapter = AsyncMSSQLTableAdapter[QueryEntity](connection, create_table=True)

        values = [uuid4().hex[:6] for _ in range(3)]
        for val in values:
            await adapter.create(name=val, status='active')

        results = []
        async for row in adapter.query(where='status=?', parameters=['active']):
            results.append(row)
        assert len(results) >= 3

        matched = results[0]
        pk_values = {k: getattr(matched, k, None) for k in adapter.primary_key}
        assert await adapter.exists(**pk_values) is True

        await adapter.delete(**pk_values)
        assert await adapter.exists(**pk_values) is False


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_upsert() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        @entity(table_name='tbl_ms_aaups')
        class UpsertEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            count: int | None = None

        adapter = AsyncMSSQLTableAdapter[UpsertEntity](connection, create_table=True)

        unique_name = f'entity_{uuid4().hex[:6]}'
        entity1 = UpsertEntity(name=unique_name, count=1)
        pk = await adapter.upsert(entity1)
        assert pk is not None
        assert pk.get('id') is not None

        read_back = await adapter.read(**pk)
        assert read_back is not None
        assert read_back.name == unique_name

        read_back.count = 3
        await adapter.upsert(read_back)
        read_back2 = await adapter.read(**pk)
        assert read_back2 is not None
        assert read_back2.count == 3


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_primary_key_property() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        @entity(table_name='tbl_ms_aapkp')
        class PKEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        adapter = AsyncMSSQLTableAdapter[PKEntity](connection, create_table=True)
        assert adapter.primary_key == ('id',)


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_uuid_field_roundtrip() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        @entity(table_name='tbl_ms_aaufr')
        class UuidEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            ref_uuid: UUID | None = None

        adapter = AsyncMSSQLTableAdapter[UuidEntity](connection, create_table=True)

        target_uuid = uuid4()
        entity1 = UuidEntity(ref_uuid=target_uuid)
        pk = await adapter.create(entity1)
        assert pk is not None

        result = await adapter.read(**pk)
        assert result is not None
        assert result.ref_uuid == target_uuid


@fact
@trait('mssql')
@trait('integration')
async def async_adapter_datetime_roundtrip() -> None:
    cxnstring = get_mssql_connectionstring()
    async with await connect_async(cxnstring) as connection:
        @entity(table_name='tbl_ch_dtr')
        class DateTimeEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            created_at: datetime | None = None

        adapter = AsyncMSSQLTableAdapter[DateTimeEntity](connection, create_table=True)

        now = datetime.now(tz=timezone.utc)
        entity1 = DateTimeEntity(created_at=now)
        pk = await adapter.create(entity1)
        assert pk is not None

        result = await adapter.read(**pk)
        assert result is not None
        assert result.created_at is not None
        assert abs((result.created_at - now).total_seconds()) < 1
