# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from deev.entities import entity, field
from deev.translation import hydrate, hydrate_mongodb, hydrate_chsql, hydrate_json, hydrate_mssql, hydrate_mysql, hydrate_sqlite, splat, splat_mongodb, splat_chsql, splat_json, splat_mssql, splat_mysql, splat_sqlite
from enum import Enum, IntEnum
from punit import fact
from typing import Any
from uuid import UUID, uuid4


@fact
def splat_empty_bvt() -> None:
    @entity
    class SEEMPTYBVT:
        attr_int: int | None = field(nullable=False)
        attr_float: float
        attr_datetime: datetime | None = field(nullable=True)
        attr_decimal: Decimal | None = field(default=None)
        attr_date: date | None = None
        attr_time: time | None = None
        attr_timedelta: timedelta | None = None
        attr_str: str | None = None
        attr_dict: dict[str, Any] | None = None
        attr_list: list[Any] | None = None
        attr_tuple: tuple[Any, ...] | None = None
        attr_uuid: UUID | None = None

    expected_entity = SEEMPTYBVT()  # type: ignore[call-arg]
    # NOTE: for coverage we inject a null-value for non-nullable
    #       field (which is unioned, while valid in Python,
    #       it is explicitly spec'd out when translating. we do this
    #       for both splatter here and hydrate further down.)
    setattr(expected_entity, 'attr_int', None)
    assert hasattr(expected_entity, 'attr_int') is False
    actual_splat = splat(expected_entity)
    assert actual_splat is not None
    assert len(actual_splat) == 10, f'expected 10, actual {len(actual_splat)}; because no attributes were initialized, but 9 of them are "implied nullable" and one of them is explicitly nullable'
    actual_splat['attr_int'] = None
    actual_entity = hydrate(SEEMPTYBVT(), actual_splat)  # type: ignore[call-arg]
    assert actual_entity is not None
    assert getattr(actual_entity, 'attr_int', object()) is not None


@fact
def splat_populated_bvt() -> None:
    """basic verification of splatter/hydrate"""
    @entity
    class SPLATPOPBVT:
        attr_int: int
        attr_float: float
        attr_datetime: datetime
        attr_date: date
        attr_time: time
        attr_timedelta: timedelta
        attr_str: str
        attr_dict: dict[str, Any]
        attr_list: list[Any]
        attr_tuple: tuple[Any, ...]
        attr_uuid: UUID
        attr_decimal: Decimal = field(mapped=False)
    expected_entity = SPLATPOPBVT(
        attr_int=1,
        attr_float=1.0,
        attr_decimal=Decimal('1.12345'),
        attr_datetime=datetime.now(timezone.utc),
        attr_date=datetime.now(timezone.utc).date(),
        attr_time=datetime.now(timezone.utc).time(),
        attr_timedelta=timedelta(
            days=1,
            seconds=2,
            microseconds=3,
            milliseconds=4,
            minutes=5,
            hours=6,
            weeks=7
        ),
        attr_str=uuid4().hex,
        attr_dict={'test': 'value'},
        attr_list=['one', 2, 3.0, Decimal('4')],
        attr_tuple=('one', 2, 3.0, Decimal('4')),
        attr_uuid=uuid4()
    )
    actual_splat = splat(expected_entity)
    assert actual_splat is not None
    assert len(actual_splat) == 11, f'expected 11, actual {len(actual_splat)}; note that `attr_decimal` is spec\'d `mapped=False` and so does not get splattered.'
    # NOTE: for coverage, we inject an 'unmapped' field; this won't hydrate (and we confirm that fact)
    actual_splat['attr_decimal'] = 123
    actual_entity = hydrate(SPLATPOPBVT(), actual_splat)  # type: ignore[call-arg]
    assert actual_entity is not None
    assert actual_entity.attr_int == expected_entity.attr_int
    assert actual_entity.attr_float == expected_entity.attr_float
    assert not hasattr(actual_entity, 'attr_decimal')
    assert actual_entity.attr_datetime == expected_entity.attr_datetime
    assert actual_entity.attr_date == expected_entity.attr_date
    assert actual_entity.attr_time == expected_entity.attr_time
    assert actual_entity.attr_timedelta == expected_entity.attr_timedelta
    assert actual_entity.attr_str == expected_entity.attr_str
    assert actual_entity.attr_dict == expected_entity.attr_dict
    assert actual_entity.attr_list == expected_entity.attr_list
    assert actual_entity.attr_tuple == expected_entity.attr_tuple
    assert actual_entity.attr_uuid == expected_entity.attr_uuid
    assert getattr(actual_entity, 'attr_decimal', None) is None


@fact
def splat_sqlite_bvt() -> None:
    """verify splatter to sql-compatible objects (and back)"""
    @entity
    class SPLATTOSQLBVT:
        attr_int: int
        attr_float: float
        attr_decimal: Decimal
        attr_datetime: datetime
        attr_date: date
        attr_time: time
        attr_timedelta: timedelta
        attr_str: str
        attr_dict: dict[str, Any]
        attr_list: list[Any]
        attr_tuple: tuple[Any, ...]
        attr_uuid: UUID
    expected_entity = SPLATTOSQLBVT(
        attr_int=1,
        attr_float=1.0,
        attr_decimal=Decimal('1.12345'),
        attr_datetime=datetime.now(timezone.utc),
        attr_date=datetime.now(timezone.utc).date(),
        attr_time=datetime.now(timezone.utc).time().replace(tzinfo=timezone.utc),
        attr_timedelta=timedelta(
            days=1,
            seconds=2,
            microseconds=3,
            milliseconds=4,
            minutes=5,
            hours=6,
            weeks=7
        ),
        attr_str=uuid4().hex,
        attr_dict={'test': 'value'},
        attr_list=['one', 2, 3.0, Decimal('4')],
        attr_tuple=('one', 2, 3.0, Decimal('4')),
        attr_uuid=uuid4()
    )
    actual_splat = splat(expected_entity, to_sql=True)
    assert actual_splat is not None
    assert len(actual_splat) == 12, f'expected 12, actual {len(actual_splat)}'
    actual_entity = hydrate(SPLATTOSQLBVT(), actual_splat, from_sql=True)  # type: ignore[call-arg]
    assert actual_entity is not None
    assert actual_entity.attr_int == expected_entity.attr_int
    assert actual_entity.attr_float == expected_entity.attr_float
    assert actual_entity.attr_decimal == expected_entity.attr_decimal
    assert actual_entity.attr_datetime == expected_entity.attr_datetime
    assert actual_entity.attr_date == expected_entity.attr_date
    assert actual_entity.attr_time == expected_entity.attr_time
    assert actual_entity.attr_timedelta == expected_entity.attr_timedelta
    assert actual_entity.attr_str == expected_entity.attr_str
    assert actual_entity.attr_dict == expected_entity.attr_dict
    assert actual_entity.attr_list == expected_entity.attr_list
    assert actual_entity.attr_tuple == expected_entity.attr_tuple
    assert actual_entity.attr_uuid == expected_entity.attr_uuid


@fact
def splat_partial_bvt() -> None:
    """verify partial splatter support"""
    @entity
    class SPLATPARTIALBVT:
        attr_int: int | None = field(nullable=False)
        attr_float: float
        attr_decimal: Decimal | None = field(default=None)
        attr_datetime: datetime | None = None
        attr_date: date | None = None
        attr_time: time | None = None
        attr_timedelta: timedelta | None = None
        attr_str: str | None = None
        attr_dict: dict[str, Any] | None = None
        attr_list: list[Any] | None = None
        attr_tuple: tuple[Any, ...] | None = None
        attr_uuid: UUID | None = None

    expected_entity = SPLATPARTIALBVT(  # type: ignore[call-arg]
        attr_int=1,
        attr_float=1.2
    )
    actual_splat = splat(expected_entity, ['attr_int'])
    assert actual_splat is not None
    assert len(actual_splat) == 1, f'expected 1, actual {len(actual_splat)}; because only partial attributes were splattered.'
    actual_entity = hydrate(SPLATPARTIALBVT(), actual_splat)  # type: ignore[call-arg]
    assert actual_entity is not None
    assert actual_entity.attr_int == expected_entity.attr_int


@fact
def hydrate_partial_bvt() -> None:
    """verify partial hydration support"""
    @entity
    class HYDRATEPARTIALBVT:
        attr_int: int | None = field(nullable=False)
        attr_float: float
        attr_decimal: Decimal | None = field(default=None)
        attr_datetime: datetime | None = None
        attr_date: date | None = None
        attr_time: time | None = None
        attr_timedelta: timedelta | None = None
        attr_str: str | None = None
        attr_dict: dict[str, Any] | None = None
        attr_list: list[Any] | None = None
        attr_tuple: tuple[Any, ...] | None = None
        attr_uuid: UUID | None = None

    expected_entity = HYDRATEPARTIALBVT(  # type: ignore[call-arg]
        attr_int=1,
        attr_float=1.2
    )
    actual_splat = splat(expected_entity)
    assert actual_splat is not None
    assert len(actual_splat) == 12, f'expected 2, actual {len(actual_splat)}'
    actual_entity = hydrate(HYDRATEPARTIALBVT(), actual_splat, ['attr_int'])  # type: ignore[call-arg]
    assert actual_entity is not None
    assert actual_entity.attr_int == expected_entity.attr_int
    assert getattr(actual_entity, 'attr_float', None) is None


@fact
def splat_targets_match_flagged_splat() -> None:
    """verify each splat_* target function matches splat with the corresponding destination flag"""
    @entity
    class SPLATTARGETBVT:
        attr_int: int
        attr_float: float
        attr_decimal: Decimal
        attr_datetime: datetime
        attr_date: date
        attr_time: time
        attr_timedelta: timedelta
        attr_str: str
        attr_dict: dict[str, Any]
        attr_list: list[Any]
        attr_tuple: tuple[Any, ...]
        attr_uuid: UUID
    expected_entity = SPLATTARGETBVT(
        attr_int=1,
        attr_float=1.0,
        attr_decimal=Decimal('1.12345'),
        attr_datetime=datetime.now(timezone.utc),
        attr_date=datetime.now(timezone.utc).date(),
        attr_time=datetime.now(timezone.utc).time().replace(tzinfo=timezone.utc),
        attr_timedelta=timedelta(days=1, seconds=2, microseconds=3),
        attr_str=uuid4().hex,
        attr_dict={'test': 'value'},
        attr_list=['one', 2, 3.0, Decimal('4')],
        attr_tuple=('one', 2, 3.0, Decimal('4')),
        attr_uuid=uuid4()
    )
    pairs = (
        ('splat_sqlite', splat_sqlite(expected_entity), splat(expected_entity, to_sql=True)),
        ('splat_mssql', splat_mssql(expected_entity), splat(expected_entity, to_mssql=True)),
        ('splat_mysql', splat_mysql(expected_entity), splat(expected_entity, to_mysql=True)),
        ('splat_chsql', splat_chsql(expected_entity), splat(expected_entity, to_chsql=True)),
        ('splat_mongodb', splat_mongodb(expected_entity), splat(expected_entity, to_bson=True)),
        ('splat_json', splat_json(expected_entity), splat(expected_entity)),
    )
    for name, actual, expected in pairs:
        assert actual == expected, f'{name} mismatch (expected={expected}, actual={actual})'
    partial_actual = splat_sqlite(expected_entity, ['attr_int'])
    partial_expected = splat(expected_entity, ['attr_int'], to_sql=True)
    assert partial_actual == partial_expected, f'(expected={partial_expected}, actual={partial_actual})'


@fact
def hydrate_targets_match_flagged_hydrate() -> None:
    """verify each hydrate_* target function matches hydrate with the corresponding source flag"""
    @entity
    class HYDRATETARGETBVT:
        attr_int: int
        attr_bool: bool
        attr_uuid: UUID
        attr_datetime: datetime
        attr_date: date
        attr_time: time
        attr_timedelta: timedelta
    data = {
        'attr_int': '1',
        'attr_bool': '1',
        'attr_uuid': '04c182b78c784285b913c8981b4727bf',
        'attr_datetime': '2023-05-19T21:43:46.539436Z',
        'attr_date': '2023-05-19',
        'attr_time': '21:43:46.539436Z',
        'attr_timedelta': 266583000321,
    }
    pairs = (
        ('hydrate_mssql', hydrate_mssql(HYDRATETARGETBVT, data), hydrate(HYDRATETARGETBVT, data, from_mssql=True)),
        ('hydrate_sqlite', hydrate_sqlite(HYDRATETARGETBVT, data), hydrate(HYDRATETARGETBVT, data, from_sql=True)),
        ('hydrate_mysql', hydrate_mysql(HYDRATETARGETBVT, data), hydrate(HYDRATETARGETBVT, data, from_mysql=True)),
        ('hydrate_chsql', hydrate_chsql(HYDRATETARGETBVT, data), hydrate(HYDRATETARGETBVT, data, from_chsql=True)),
        ('hydrate_mongodb', hydrate_mongodb(HYDRATETARGETBVT, data), hydrate(HYDRATETARGETBVT, data, from_bson=True)),
        ('hydrate_json', hydrate_json(HYDRATETARGETBVT, data), hydrate(HYDRATETARGETBVT, data)),
    )
    for name, actual, expected in pairs:
        assert splat_json(actual) == splat_json(expected), f'{name} mismatch (expected={splat_json(expected)}, actual={splat_json(actual)})'
    partial_actual = splat_json(hydrate_sqlite(HYDRATETARGETBVT, data, ['attr_int']))
    partial_expected = splat_json(hydrate(HYDRATETARGETBVT, data, ['attr_int'], from_sql=True))
    assert partial_actual == partial_expected, f'(expected={partial_expected}, actual={partial_actual})'
