# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect
from deev.mssql.mssql_table_adapter import MSSQLTableAdapter
from mssql_python import DatabaseError
from punit import fact, trait
from typing import Any
from uuid import UUID, uuid4


@fact
@trait('mssql')
@trait('integration')
def where_string_longer_than_column_returns_no_rows() -> None:
    """
    Regression: mssql_python sized string parameters from the value, so a
    value longer than the target column raised "String data, right truncation"
    even in WHERE comparisons that should simply return no rows.
    """
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_strlen_where')
        class StrLenEntity:
            text: str = field(max=20)
            id: int = field(autoincrement=True, primary_key=True, default=0)

        adapter = MSSQLTableAdapter[StrLenEntity](connection, create_table=True, use_setinputsizes=True)
        cursor = connection.cursor()
        cursor.execute("IF OBJECT_ID('dbo.tbl_ms_strlen_where','U') IS NOT NULL DROP TABLE [tbl_ms_strlen_where]")
        cursor.close()
        entity_key = adapter.create(StrLenEntity(text='hello'))
        try:
            # 30-char value vs NVARCHAR(20) column: must return no rows, not raise
            selected = list(adapter.query(where='text=?', parameters=['x' * 30]))
            assert len(selected) == 0
            # %? placeholder style resolves the same way
            selected = list(adapter.query(where='text=%?', parameters=['x' * 30]))
            assert len(selected) == 0
            # a matching value still returns the row
            selected = list(adapter.query(where='text=?', parameters=['hello']))
            assert len(selected) == 1
            assert selected[0].text == 'hello'
            # insert of an over-long value still fails (cleanly, on the server)
            try:
                adapter.create(StrLenEntity(text='y' * 30))
            except DatabaseError:
                pass
            else:
                raise AssertionError('expected truncation error for over-long insert was not observed.')
        finally:
            adapter.delete(**entity_key)


@fact
@trait('mssql')
@trait('integration')
def read_with_string_key_longer_than_column_returns_none() -> None:
    """
    Regression: string primary key lookups with a key longer than the column
    raised "String data, right truncation" instead of returning None/False.
    """
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_strlen_key')
        class StrKeyEntity:
            skey: str = field(primary_key=True, max=20)
            value: str = field(max=20)

        adapter = MSSQLTableAdapter[StrKeyEntity](connection, create_table=True, use_setinputsizes=True)
        cursor = connection.cursor()
        cursor.execute("IF OBJECT_ID('dbo.tbl_ms_strlen_key','U') IS NOT NULL DROP TABLE [tbl_ms_strlen_key]")
        cursor.close()
        entity_key = adapter.create(StrKeyEntity(skey='the-key', value='a-value'))
        try:
            assert adapter.read(**entity_key) is not None
            assert adapter.exists(**entity_key) is True
            # 30-char key vs NVARCHAR(20) column: None/False, not an error
            assert adapter.read(skey='x' * 30) is None
            assert adapter.exists(skey='x' * 30) is False
            # an over-long key still cannot be created
            try:
                adapter.create(StrKeyEntity(skey='z' * 30, value='v'))
            except DatabaseError:
                pass
            else:
                raise AssertionError('expected truncation error for over-long key was not observed.')
        finally:
            adapter.delete(**entity_key)


@fact
@trait('mssql')
@trait('integration')
def roundtrip_with_declared_input_sizes() -> None:
    """
    Full CRUD round-trip across the types the input-size declarations cover,
    ensuring the explicit declarations do not alter stored values.
    """
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_strlen_round')
        class RoundTripEntity:
            big: int | None = field(dbtype='BIGINT')
            s_plain: str = field(max=50)
            s_max: str = field(max=50)
            id: int = field(autoincrement=True, primary_key=True, default=0)
            n: int | None = None
            b: bool | None = None
            f: float | None = None
            d: Decimal | None = None
            s_json: dict[str, Any] | None = None
            uid: UUID | None = None
            dt: datetime | None = None
            td: timedelta | None = None

        adapter = MSSQLTableAdapter[RoundTripEntity](connection, create_table=True, use_setinputsizes=True)
        cursor = connection.cursor()
        cursor.execute("IF OBJECT_ID('dbo.tbl_ms_strlen_round','U') IS NOT NULL DROP TABLE [tbl_ms_strlen_round]")
        cursor.close()
        now = datetime.now(tz=timezone.utc)
        delta = timedelta(days=1, hours=2, microseconds=345)
        uid_value = uuid4()
        entity_key = adapter.create(RoundTripEntity(
            n=42,
            big=9999999999,
            b=True,
            f=3.14159,
            d=Decimal('1234.5678901234'),
            s_max='s-max-value',
            s_plain='a plain string value beyond the default twenty',
            s_json={'a': 1, 'b': [2, 3]},
            uid=uid_value,
            dt=now,
            td=delta
        ))
        try:
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.n == 42
            assert data.big == 9999999999
            assert data.b is True
            assert data.f == 3.14159
            assert data.d == Decimal('1234.5678901234')
            assert data.s_max == 's-max-value'
            assert data.s_plain == 'a plain string value beyond the default twenty'
            assert data.s_json == {'a': 1, 'b': [2, 3]}
            assert data.uid is not None and data.uid.hex == uid_value.hex
            assert data.dt is not None and data.dt.tzinfo is not None
            assert data.td == delta

            data.s_max = 'an updated s-max value'
            adapter.update(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.s_max == 'an updated s-max value'

            adapter.upsert(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.s_max == 'an updated s-max value'

            selected = list(adapter.query(where='n=? AND s_max LIKE ?', parameters=[42, 'an updated%']))
            assert len(selected) == 1

            # s_plain is NVARCHAR(50); a 45-char value round-trips
            data.s_plain = 'z' * 45
            adapter.update(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.s_plain == 'z' * 45
        finally:
            adapter.delete(**entity_key)


@fact
@trait('mssql')
@trait('integration')
def long_strings_roundtrip() -> None:
    """
    Values beyond the 4000-char inline limit bind as NVARCHAR(MAX), and a
    ``max`` above 4000 maps to an ``NVARCHAR(MAX)`` column.
    """
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    with connect(cxnstring) as connection:
        @entity(table_name='tbl_ms_strlen_long')
        class LongJsonEntity:
            long_text: str = field(max=10000)
            id: int = field(autoincrement=True, primary_key=True, default=0)
            blob: dict[str, Any] | None = None

        adapter = MSSQLTableAdapter[LongJsonEntity](connection, create_table=True, use_setinputsizes=True)
        cursor = connection.cursor()
        cursor.execute("IF OBJECT_ID('dbo.tbl_ms_strlen_long','U') IS NOT NULL DROP TABLE [tbl_ms_strlen_long]")
        cursor.close()
        long_json = {'data': 'x' * 9000}
        entity_key = adapter.create(LongJsonEntity(blob=long_json, long_text='q' * 9500))
        try:
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.blob == long_json
            assert data.long_text == 'q' * 9500
        finally:
            adapter.delete(**entity_key)
