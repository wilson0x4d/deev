# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from deev.entities import entity, field
from deev.translation import splat, hydrate
from punit import fact
from typing import Any, Optional
from uuid import UUID, uuid4


@fact
def splat_empty_bvt() -> None:
    @entity
    class SEEMPTYBVT:
        attr_int: Optional[int] = field(nullable=False)
        attr_float: float
        attr_datetime: Optional[datetime] = field(nullable=True)
        attr_decimal: Optional[Decimal] = field(default=None)
        attr_date: Optional[date] = None
        attr_time: Optional[time] = None
        attr_timedelta: Optional[timedelta] = None
        attr_str: Optional[str] = None
        attr_dict: Optional[dict[str, Any]] = None
        attr_list: Optional[list[Any]] = None
        attr_tuple: Optional[tuple[Any, ...]] = None
        attr_uuid: Optional[UUID] = None

    expected_entity = SEEMPTYBVT()  # type: ignore[call-arg]
    # NOTE: for coverage we inject a null-value for non-nullable
    #       field (which is unioned Optional, while valid in Python,
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
    assert actual_entity.attr_uuid.hex == expected_entity.attr_uuid.hex
    assert getattr(actual_entity, 'attr_decimal', None) is None


@fact
def splat_to_sql_bvt() -> None:
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
    assert actual_entity.attr_datetime.isoformat() == expected_entity.attr_datetime.isoformat(), f'{actual_entity.attr_datetime.isoformat()} != {expected_entity.attr_datetime.isoformat()}'
    assert actual_entity.attr_date == expected_entity.attr_date
    assert actual_entity.attr_time == expected_entity.attr_time
    assert actual_entity.attr_timedelta == expected_entity.attr_timedelta
    assert actual_entity.attr_str == expected_entity.attr_str
    assert actual_entity.attr_dict == expected_entity.attr_dict
    assert actual_entity.attr_list == expected_entity.attr_list
    assert actual_entity.attr_tuple == expected_entity.attr_tuple
    assert actual_entity.attr_uuid.hex == expected_entity.attr_uuid.hex


@fact
def splat_partial_bvt() -> None:
    """verify partial splatter support"""
    @entity
    class SPLATPARTIALBVT:
        attr_int: Optional[int] = field(nullable=False)
        attr_float: float
        attr_decimal: Optional[Decimal] = field(default=None)
        attr_datetime: Optional[datetime] = None
        attr_date: Optional[date] = None
        attr_time: Optional[time] = None
        attr_timedelta: Optional[timedelta] = None
        attr_str: Optional[str] = None
        attr_dict: Optional[dict[str, Any]] = None
        attr_list: Optional[list[Any]] = None
        attr_tuple: Optional[tuple[Any, ...]] = None
        attr_uuid: Optional[UUID] = None

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
        attr_int: Optional[int] = field(nullable=False)
        attr_float: float
        attr_decimal: Optional[Decimal] = field(default=None)
        attr_datetime: Optional[datetime] = None
        attr_date: Optional[date] = None
        attr_time: Optional[time] = None
        attr_timedelta: Optional[timedelta] = None
        attr_str: Optional[str] = None
        attr_dict: Optional[dict[str, Any]] = None
        attr_list: Optional[list[Any]] = None
        attr_tuple: Optional[tuple[Any, ...]] = None
        attr_uuid: Optional[UUID] = None

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
