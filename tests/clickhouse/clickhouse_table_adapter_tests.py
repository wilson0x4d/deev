# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.clickhouse import ClickHouseProxyConnection, ClickHouseTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait


@fact
@trait('clickhouse')
@trait('integration')
def basic_verification() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_ch_bvt')
        class BasicEntity:
            id: str = field(primary_key=True)
            example: int | None = None
            example_text: str | None = None
            other: UUID | None = None
            another: bool | None = None
            floaty: float | None = None
            backed_value: int | None = None
            x: dict[str, str] | None = None
            y: list[int] | None = None
            z: tuple[str, int] | None = None
            dt: datetime | None = None

        with connect(cxnstring) as connection:
            assert isinstance(connection, ClickHouseProxyConnection)
            adapter = ClickHouseTableAdapter[BasicEntity](connection, create_table=True)

            entity1 = BasicEntity(
                id=uuid4().hex,
                example=123,
                other=uuid4(),
                dt=datetime.now(tz=timezone.utc)
            )
            entity_key = adapter.create(entity1)
            assert entity_key is not None
            assert entity_key.get('id') is not None

            data = adapter.read(**entity_key)
            assert data is not None

            data.example_text = 'updated'
            adapter.upsert(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.example_text == 'updated'

            selected = []
            for row in adapter.query(where='exampleText=%?', parameters=['updated']):
                selected.append(row)
            assert len(selected) > 0

            adapter.delete(**entity_key)
            existence = adapter.exists(**entity_key)
            assert existence is False
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
def timedelta_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_ch_tdr')
        class TimedeltaEntity:
            id: str = field(primary_key=True)
            duration: timedelta | None = None

        with connect(cxnstring) as connection:
            assert isinstance(connection, ClickHouseProxyConnection)
            adapter = ClickHouseTableAdapter[TimedeltaEntity](connection, create_table=True)

            target = timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=567)
            entity1 = TimedeltaEntity(id=uuid4().hex, duration=target)
            pk = adapter.create(entity1)
            assert pk is not None
            assert pk.get('id') is not None

            result = adapter.read(**pk)
            assert result is not None
            assert result.duration is not None
            assert result.duration == target
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
def datetime_aware_non_utc_roundtrip() -> None:
    """Timezone-aware non-UTC datetimes are normalized to UTC for storage (DateTime64 cannot store offsets) and read back as UTC."""
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_ch_dtz')
        class DateTimeEntity:
            id: str = field(primary_key=True)
            created_at: datetime | None = None

        with connect(cxnstring) as connection:
            assert isinstance(connection, ClickHouseProxyConnection)
            adapter = ClickHouseTableAdapter[DateTimeEntity](connection, create_table=True)
            uid = f'dtz-{uuid4().hex[:8]}'
            original = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone(timedelta(hours=5)))
            adapter.create(DateTimeEntity(id=uid, created_at=original))

            result = adapter.read(id=uid)
            assert result is not None
            assert result.created_at is not None
            assert result.created_at.tzinfo is not None, f'expected an aware datetime, got {result.created_at!r}'
            assert result.created_at == original.astimezone(timezone.utc), f'expected a UTC datetime, got {result.created_at!r}'
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass
