# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from deev import entity, field
from deev.common import DbError
from deev.entities import get_entity_spec
from deev.clickhouse import ClickHouseTypeMapper
from punit import fact, inlinedata, theory, trait
from typing import Any, Mapping
from uuid import UUID


@entity
class TypeMapperTestEntity:
    num_int: int
    num_float: float
    num_decimal: Decimal
    dt_datetime: datetime
    dt_date: date
    dt_time: time
    dt_timedelta: timedelta
    complex_dict: dict[str, int]
    complex_list: list[float]
    complex_tuple: tuple[Decimal]
    complex_set: set[Any]
    complex_map: Mapping
    bit: bool
    uid: UUID
    min_max_str: str = field(min=5, max=5)
    min_str: str = field(min=5)
    max_str: str = field(max=50)
    with_dbtype: int = field(dbtype='UInt64')


@fact
@trait('clickhouse')
@trait('unit')
def when_non_existent_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('non_existent')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@theory
@inlinedata('num_int', 'Int64')
@inlinedata('num_float', 'Float64')
@inlinedata('num_decimal', 'Decimal(20, 10)')
@inlinedata('dt_datetime', 'DateTime64(6)')
@inlinedata('dt_date', 'Date32')
@inlinedata('dt_time', 'String')
@inlinedata('dt_timedelta', 'Int64')
@inlinedata('complex_dict', 'String')
@inlinedata('complex_list', 'String')
@inlinedata('complex_tuple', 'String')
@inlinedata('complex_set', 'String')
@inlinedata('complex_map', 'String')
@inlinedata('bit', 'Bool')
@inlinedata('uid', 'String')
@inlinedata('min_max_str', 'FixedString(5)')
@inlinedata('min_str', 'String')
@inlinedata('max_str', 'FixedString(50)')
@inlinedata('with_dbtype', 'UInt64')
@trait('clickhouse')
@trait('unit')
def expected_mapping(field_name: str, dbtype: str) -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    actual = mapper.get_provider_type(field_name)
    assert actual == dbtype, f'expected "{dbtype}" for "{field_name}", got "{actual}"'
