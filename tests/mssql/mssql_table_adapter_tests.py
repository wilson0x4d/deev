# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect
from deev.mssql.mssql_table_adapter import MSSQLTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait
from typing import Any


@fact
@trait('mssql')
@trait('integration')
def basic_verification() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    unique_text = uuid4().hex[:6]
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_bvt')
        class BasicEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            example: int | None = None
            example_text: str | None = None
            other: UUID | None = None
            another: bool | None = None
            floaty: float | None = None
            backed_value: int | None = None
            x: dict[str, Any] | None = None
            y: list[int] | None = None
            z: tuple[str, int] | None = None
            dt: datetime | None = None
            td: timedelta | None = None

        adapter = MSSQLTableAdapter[BasicEntity](connection, create_table=True)

        entity1 = BasicEntity(
            example=123,
            other=uuid4(),
            dt=datetime.now(tz=timezone.utc)
        )
        entity_key = adapter.create(entity1)

        assert entity_key is not None
        assert entity_key.get('id') is not None
        assert entity_key.get('id', 0) > 0

        data = adapter.read(**entity_key)
        assert data is not None

        data.example_text = unique_text
        adapter.upsert(data)
        data = adapter.read(**entity_key)
        assert data is not None

        data.example_text = unique_text
        adapter.upsert(data)
        data = adapter.read(**entity_key)
        assert data is not None
        assert data.example_text == unique_text
        assert data.example == entity1.example
        assert data.other is not None
        assert entity1.other is not None
        assert data.other.hex == entity1.other.hex

        selected = []
        for row in adapter.query(
            where='example_text=?',
            parameters=[unique_text],
            orderby='id DESC'
        ):
            selected.append(row)
        assert len(selected) > 0

        adapter.delete(**entity_key)
        existence = adapter.exists(**entity_key)
        assert existence is False


@fact
@trait('mssql')
@trait('integration')
def create_with_kwargs() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity
        class KwargsEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        adapter = MSSQLTableAdapter[KwargsEntity](connection, create_table=True)

        value = uuid4().hex[:6]
        key = adapter.create(value=value)
        assert key is not None
        assert key.get('id') is not None

        result = adapter.read(**key)
        assert result is not None
        assert result.value == value


@fact
@trait('mssql')
@trait('integration')
def query_and_delete() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ch_qad')
        class QueryEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            status: str | None = None

        adapter = MSSQLTableAdapter[QueryEntity](connection, create_table=True)

        values = [uuid4().hex[:6] for _ in range(3)]
        for val in values:
            adapter.create(name=val, status='active')

        results = list(adapter.query(where='status=?', parameters=['active']))
        assert len(results) >= 3

        matched = results[0]
        pk_values = {k: getattr(matched, k, None) for k in adapter.primary_key}
        assert adapter.exists(**pk_values) is True

        adapter.delete(**pk_values)
        assert adapter.exists(**pk_values) is False


@fact
@trait('mssql')
@trait('integration')
def upsert() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_ups')
        class UpsertEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None
            count: int | None = None

        adapter = MSSQLTableAdapter[UpsertEntity](connection, create_table=True)

        unique_name = f'entity_{uuid4().hex[:6]}'
        entity1 = UpsertEntity(name=unique_name, count=1)
        pk = adapter.upsert(entity1)
        assert pk is not None
        assert pk.get('id') is not None

        read_back = adapter.read(**pk)
        assert read_back is not None
        assert read_back.name == unique_name

        read_back.count = 3
        adapter.upsert(read_back)
        read_back2 = adapter.read(**pk)
        assert read_back2 is not None
        assert read_back2.count == 3


@fact
@trait('mssql')
@trait('integration')
def primary_key_property() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_pkp')
        class PKEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            value: str | None = None

        adapter = MSSQLTableAdapter[PKEntity](connection, create_table=True)
        assert adapter.primary_key == ('id',)


@fact
@trait('mssql')
@trait('integration')
def uuid_field_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_ufr')
        class UuidEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            ref_uuid: UUID | None = None

        adapter = MSSQLTableAdapter[UuidEntity](connection, create_table=True)

        target_uuid = uuid4()
        entity1 = UuidEntity(ref_uuid=target_uuid)
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(**pk)
        assert result is not None
        assert result.ref_uuid == target_uuid


@fact
@trait('mssql')
@trait('integration')
def datetime_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_dtr')
        class DateTimeEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            created_at: datetime | None = None

        adapter = MSSQLTableAdapter[DateTimeEntity](connection, create_table=True)

        now = datetime.now(tz=timezone.utc)
        entity1 = DateTimeEntity(created_at=now)
        pk = adapter.create(entity1)
        assert pk is not None

        result = adapter.read(**pk)
        assert result is not None
        assert result.created_at is not None
        assert abs((result.created_at - now).total_seconds()) < 1


@fact
@trait('mssql')
@trait('integration')
def bigint_autoincrement() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity
        class BigintEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None

        adapter = MSSQLTableAdapter[BigintEntity](connection, create_table=True)
        entity1 = BigintEntity(name=f'bigint_{uuid4().hex[:6]}')
        pk = adapter.create(entity1)
        assert pk is not None
        assert pk.get('id') is not None
        assert pk.get('id', 0) > 0
        result = adapter.read(**pk)
        assert result is not None
        assert result.name == entity1.name


@fact
@trait('mssql')
@trait('integration')
def multi_column_primary_key() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity
        class MultiPkEntity:
            country_code: str = field(primary_key=True)
            city_name: str = field(primary_key=True)
            population: int | None = None

        adapter = MSSQLTableAdapter[MultiPkEntity](connection, create_table=True)
        unique_prefix = uuid4().hex[:4]
        country_a = f'ZZ_{unique_prefix}'
        country_b = f'ZZ_{uuid4().hex[:4]}'
        adapter.create(country_code=country_a, city_name='NYC', population=8000000)
        adapter.create(country_code=country_b, city_name='LDN', population=9000000)
        result = adapter.read(country_code=country_a, city_name='NYC')
        assert result is not None
        assert result.population == 8000000
        adapter.delete(country_code=country_a, city_name='NYC')
        result2 = adapter.read(country_code=country_a, city_name='NYC')
        assert result2 is None
