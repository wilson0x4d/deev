# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.sqlite import SQLiteTableAdapter
import os
from punit import fact, trait
import shutil
from typing import Any
from uuid import UUID, uuid4


@fact
@trait('sqlite')
@trait('integration')
def basic_verification() -> None:
    #
    # mutate configuration to generate a unique database
    #
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_sl_bvt')
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
        with connect(cxnstring) as connection:
            #
            # ..create a table adapter _and_ create a backing table for `BasicEntity`
            #
            adapter = SQLiteTableAdapter[BasicEntity](connection, create_table=True)
            #
            # ..create a BasicEntity instance in the database
            #
            entity1 = BasicEntity(
                example=123,
                other=uuid4(),
                dt=datetime.now(tz=timezone.utc)
            )
            entity_key = adapter.create(entity1)
            #
            # ..assert a valid key has been returned
            #
            assert entity_key is not None
            assert entity_key.get('id') is not None
            assert entity_key.get('id', 0) > 0
            #
            # ..assert we can read the entity back using the key
            #
            data = adapter.read(**entity_key)
            assert data is not None
            #
            # ..assert we can mutate the entity
            data.example_text = 'updated'
            adapter.upsert(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.example_text == 'updated'
            assert data.example == entity1.example
            assert data.other is not None
            assert entity1.other is not None
            assert data.other.hex == entity1.other.hex
            #
            # ..assert we can query for the entity
            #
            selected = []
            for row in adapter.query(
                where='example_text=%?',
                parameters=['updated'],
                orderby='id DESC'
            ):
                selected.append(row)
            assert len(selected) > 0
            #
            # ..assert deletions
            #
            adapter.delete(**entity_key)
            existence = adapter.exists(**entity_key)
            assert existence is False
    finally:
        #
        # ..remove the test database we created
        #
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        assert os.path.exists(database_path)
        shutil.rmtree(database_path)
        assert not os.path.exists(database_path)


@fact
@trait('sqlite')
@trait('integration')
def datetime_aware_non_utc_roundtrip() -> None:
    """Timezone-aware datetimes retain their UTC offset through a roundtrip (stored as TEXT with the offset)."""
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_sl_dtz')
        class AwareDtEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            ts: datetime | None = None

        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[AwareDtEntity](connection, create_table=True)
            original = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone(timedelta(hours=5)))
            pk = adapter.create(AwareDtEntity(ts=original))
            assert pk is not None

            # The underlying storage is TEXT and must retain the offset.
            cursor = connection.cursor()
            cursor.execute('SELECT [ts] FROM [tbl_sl_dtz] WHERE [id] = %?', (pk['id'],))
            stored = cursor.fetchone()
            assert stored is not None
            assert '+05:00' in str(stored[0]), f'expected the offset in the stored value, got {stored[0]!r}'

            result = adapter.read(**pk)
            assert result is not None
            assert result.ts is not None
            assert result.ts == original, f'expected the offset to be preserved, got {result.ts!r}'
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        assert os.path.exists(database_path)
        shutil.rmtree(database_path)
        assert not os.path.exists(database_path)


@fact
@trait('sqlite')
@trait('integration')
def datetime_naive_roundtrip_treated_as_utc() -> None:
    """Naive datetimes are treated as UTC, stored with the UTC offset, and read back as timezone-aware."""
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_sl_dtz')
        class AwareDtEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            ts: datetime | None = None

        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[AwareDtEntity](connection, create_table=True)
            original = datetime(2024, 1, 15, 12, 30, 45)
            expected = original.replace(tzinfo=timezone.utc)
            pk = adapter.create(AwareDtEntity(ts=original))
            assert pk is not None

            result = adapter.read(**pk)
            assert result is not None
            assert result.ts is not None
            assert result.ts.tzinfo is not None, f'expected an aware datetime, got {result.ts!r}'
            assert result.ts == expected, f'expected naive to be treated as UTC, got {result.ts!r}'
            assert result.ts.utcoffset() == timedelta(0), f'expected a UTC offset, got {result.ts!r}'
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        assert os.path.exists(database_path)
        shutil.rmtree(database_path)
        assert not os.path.exists(database_path)


@fact
@trait('sqlite')
@trait('integration')
def timedelta_roundtrip() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity(table_name='tbl_sl_tdr')
        class TimedeltaEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            duration: timedelta | None = None

        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[TimedeltaEntity](connection, create_table=True)

            target = timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=567)
            entity1 = TimedeltaEntity(duration=target)
            pk = adapter.create(entity1)
            assert pk is not None
            assert pk.get('id') is not None

            result = adapter.read(**pk)
            assert result is not None
            assert result.duration is not None
            assert result.duration == target
    finally:
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        assert os.path.exists(database_path)
        shutil.rmtree(database_path)
        assert not os.path.exists(database_path)


@fact
@trait('sqlite')
def query_and_read_roundtrip_on_temp_database() -> None:
    """read() and query() hydrate rows end-to-end, applying field defaults for NULL columns."""
    import tempfile

    db_dir = tempfile.mkdtemp(prefix='deev_qrt_')
    db_name = f'deev_qrt_{uuid4().hex}.db'
    try:
        @entity(table_name='tbl_qrt')
        class QrtEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            example: int | None = None
            name: str | None = None
            note: str | None = field(default='default-note')

        cxnstring = ConnectionString(f'Server={db_dir};Database={db_name};Provider=sqlite3')
        with connect(cxnstring) as connection:
            adapter = SQLiteTableAdapter[QrtEntity](connection, create_table=True)
            pk = adapter.create(QrtEntity(example=42, name='first', note=None))
            assert pk is not None, 'expected a primary key to be returned'
            row = adapter.read(**pk)
            assert row is not None, 'expected a row to be read back'
            assert row.example == 42, f'expected example 42, got {row.example}'
            assert row.name == 'first', f'expected name "first", got {row.name}'
            assert row.note == 'default-note', f'expected the field default to be applied for a NULL column, got {row.note}'
            selected = [e for e in adapter.query(where='name=%?', parameters=['first'], orderby='id DESC')]
            assert len(selected) == 1, f'expected 1 row from query, got {len(selected)}'
            assert selected[0].example == 42, f'expected example 42, got {selected[0].example}'
            assert selected[0].name == 'first', f'expected name "first", got {selected[0].name}'
            assert selected[0].note == 'default-note', f'expected the field default to be applied for a NULL column, got {selected[0].note}'
            adapter.delete(**pk)
            assert adapter.read(**pk) is None, 'expected no row after delete'
    finally:
        shutil.rmtree(db_dir, ignore_errors=True)
