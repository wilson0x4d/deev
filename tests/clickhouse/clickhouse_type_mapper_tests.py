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

from deev.clickhouse.clickhouse_type_mapper import ClickHouseNativeMapError


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
    complex_map: Mapping[str, int]
    bit: bool
    uid: UUID
    min_max_str: str = field(min=5, max=5)
    min_str: str = field(min=5)
    max_str: str = field(max=50)
    with_dbtype: int = field(dbtype='UInt64')

    # bare/non-parameterized forms (fall back to String)
    bare_list: list
    bare_dict: dict
    bare_tuple: tuple


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


@fact
@trait('clickhouse')
@trait('unit')
def list_any_raises() -> None:
    @entity
    class ErrorTestEntity:
        any_set: set[Any]

    entity_spec = get_entity_spec(ErrorTestEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('any_set')
    except ClickHouseNativeMapError:
        pass
    else:
        raise AssertionError('expected ClickHouseNativeMapError was not observed.')


@fact
@trait('clickhouse')
@trait('unit')
def dict_any_val_raises() -> None:
    @entity
    class ErrorTestEntity:
        any_dict: dict[str, Any]

    entity_spec = get_entity_spec(ErrorTestEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('any_dict')
    except ClickHouseNativeMapError:
        pass
    else:
        raise AssertionError('expected ClickHouseNativeMapError was not observed.')


@fact
@trait('clickhouse')
@trait('unit')
def dict_any_key_raises() -> None:
    @entity
    class ErrorTestEntity:
        any_key_dict: dict[Any, int]

    entity_spec = get_entity_spec(ErrorTestEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('any_key_dict')
    except ClickHouseNativeMapError:
        pass
    else:
        raise AssertionError('expected ClickHouseNativeMapError was not observed.')


@fact
@trait('clickhouse')
@trait('unit')
def bare_collection_fallbacks_to_string() -> None:
    @entity
    class BcEntity:
        bl: list
        bd: dict
        bt: tuple

    entity_spec = get_entity_spec(BcEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    assert mapper.get_provider_type('bl') == 'String'
    assert mapper.get_provider_type('bd') == 'String'
    assert mapper.get_provider_type('bt') == 'String'


@theory
@inlinedata('num_int', 'Int64')
@inlinedata('num_float', 'Float64')
@inlinedata('num_decimal', 'Decimal128(18)')
@inlinedata('dt_datetime', 'DateTime64(6)')
@inlinedata('dt_date', 'Date32')
@inlinedata('dt_time', 'String')
@inlinedata('dt_timedelta', 'Int64')
@inlinedata('complex_dict', 'Map(String, Int64)')
@inlinedata('complex_list', 'Array(Float64)')
@inlinedata('complex_tuple', 'Tuple(Decimal128(18))')
@inlinedata('complex_map', 'Map(String, Int64)')
@inlinedata('bit', 'Bool')
@inlinedata('uid', 'UUID')
@inlinedata('min_max_str', 'String')
@inlinedata('min_str', 'String')
@inlinedata('max_str', 'String')
@inlinedata('with_dbtype', 'UInt64')
@inlinedata('bare_list', 'String')
@inlinedata('bare_dict', 'String')
@inlinedata('bare_tuple', 'String')
@trait('clickhouse')
@trait('unit')
def expected_mapping(field_name: str, dbtype: str) -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = ClickHouseTypeMapper(entity_spec)
    actual = mapper.get_provider_type(field_name)
    assert actual == dbtype, f'expected "{dbtype}" for "{field_name}", got "{actual}"'
