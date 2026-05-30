# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from deev import entity, field
from deev.common import DbError
from deev.entities import get_entity_spec
from deev.mysql import MysqlTypeMapper
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
    with_sqltype: int = field(sqltype='VARCHAR(42)')


@fact
@trait('mysql')
def when_unmapped_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = MysqlTypeMapper(entity_spec)
    try:
        mapper.get_sqltype('unmappable')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@fact
@trait('mysql')
def when_non_existent_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = MysqlTypeMapper(entity_spec)
    try:
        mapper.get_sqltype('non_existent')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@theory
@inlinedata('min_max_str', 'CHAR(5)')
@inlinedata('min_str', 'VARCHAR(20)')
@inlinedata('max_str', 'VARCHAR(50)')
@inlinedata('num_int', 'BIGINT')
@inlinedata('num_float', 'DOUBLE')
@inlinedata('num_decimal', 'DECIMAL(20,10)')
@inlinedata('dt_datetime', 'DATETIME(6)')
@inlinedata('dt_date', 'DATE')
@inlinedata('dt_time', 'TIME(6)')
@inlinedata('dt_timedelta', 'BIGINT')
@inlinedata('complex_dict', 'MEDIUMTEXT')
@inlinedata('complex_list', 'MEDIUMTEXT')
@inlinedata('complex_tuple', 'MEDIUMTEXT')
@inlinedata('complex_set', 'MEDIUMTEXT')
@inlinedata('complex_map', 'MEDIUMTEXT')
@inlinedata('bit', 'BIT')
@inlinedata('uid', 'CHAR(32)')
@inlinedata('with_sqltype', 'VARCHAR(42)')
@trait('mysql')
def expected_mapping(field_name: str, sqltype: str) -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = MysqlTypeMapper(entity_spec)
    actual = mapper.get_sqltype(field_name)
    assert actual == sqltype, f'expected "{sqltype}" for "{field_name}", got "{actual}"'
