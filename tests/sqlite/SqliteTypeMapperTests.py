# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from deev import entity, field
from deev.common import DbError
from deev.entities import get_entity_spec
from deev.sqlite import SqliteTypeMapper
from punit import fact, inlinedata, theory, trait
from typing import Any, Callable, Mapping
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
    unmappable: Callable
    min_max_str: str = field(min=5, max=5)
    min_str: str = field(min=5)
    max_str: str = field(max=50)
    with_dbtype: int = field(dbtype='TEXT')


@fact
@trait('sqlite3')
def when_unmapped_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = SqliteTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('unmappable')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@fact
@trait('sqlite3')
def when_non_existent_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = SqliteTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('non_existent')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@theory
@inlinedata('min_max_str', 'TEXT')
@inlinedata('min_str', 'TEXT')
@inlinedata('max_str', 'TEXT')
@inlinedata('num_int', 'INTEGER')
@inlinedata('num_float', 'REAL')
@inlinedata('num_decimal', 'NUMERIC')
@inlinedata('dt_datetime', 'DATETIME')
@inlinedata('dt_date', 'DATE')
@inlinedata('dt_time', 'TIME')
@inlinedata('dt_timedelta', 'INTEGER')
@inlinedata('complex_dict', 'TEXT')
@inlinedata('complex_list', 'TEXT')
@inlinedata('complex_tuple', 'TEXT')
@inlinedata('complex_set', 'TEXT')
@inlinedata('complex_map', 'TEXT')
@inlinedata('bit', 'INTEGER')
@inlinedata('uid', 'TEXT')
@inlinedata('with_dbtype', 'TEXT')
@trait('sqlite3')
def expected_mapping(field_name: str, dbtype: str) -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = SqliteTypeMapper(entity_spec)
    actual = mapper.get_provider_type(field_name)
    assert actual == dbtype, f'expected "{dbtype}" for "{field_name}", got "{actual}"'
