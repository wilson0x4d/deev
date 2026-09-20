# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from deev import entity, field
from deev.common import DbError
from deev.entities import get_entity_spec
from deev.mssql import MSSQLTypeMapper
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
    with_dbtype: int = field(dbtype='VARCHAR(42)')
    big_int: int = field(dbtype='BIGINT')


@fact
@trait('mssql')
@trait('unit')
def when_unmapped_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('unmappable')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@fact
@trait('mssql')
@trait('unit')
def when_non_existent_then_raises() -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    try:
        mapper.get_provider_type('non_existent')
    except DbError:
        pass
    else:
        raise AssertionError('expected DbError was not observed.')


@fact
@trait('mssql')
@trait('unit')
def bare_collection_fallbacks() -> None:
    @entity
    class BareCollectionEntity:
        bare_list: list
        bare_dict: dict
        bare_tuple: tuple

    entity_spec = get_entity_spec(BareCollectionEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    assert mapper.get_provider_type('bare_list') == 'NVARCHAR(MAX)'
    assert mapper.get_provider_type('bare_dict') == 'NVARCHAR(MAX)'
    assert mapper.get_provider_type('bare_tuple') == 'NVARCHAR(MAX)'


@theory
@inlinedata('min_max_str', 'NCHAR(5)')
@inlinedata('min_str', 'NVARCHAR(20)')
@inlinedata('max_str', 'NVARCHAR(50)')
@inlinedata('num_int', 'INT')
@inlinedata('num_float', 'FLOAT')
@inlinedata('num_decimal', 'DECIMAL(20,10)')
@inlinedata('dt_datetime', 'DATETIME2(6)')
@inlinedata('dt_date', 'DATE')
@inlinedata('dt_time', 'TIME(6)')
@inlinedata('dt_timedelta', 'BIGINT')
@inlinedata('complex_dict', 'NVARCHAR(MAX)')
@inlinedata('complex_list', 'NVARCHAR(MAX)')
@inlinedata('complex_tuple', 'NVARCHAR(MAX)')
@inlinedata('complex_set', 'NVARCHAR(MAX)')
@inlinedata('complex_map', 'NVARCHAR(MAX)')
@inlinedata('bit', 'BIT')
@inlinedata('uid', 'UNIQUEIDENTIFIER')
@inlinedata('with_dbtype', 'VARCHAR(42)')
@inlinedata('big_int', 'BIGINT')
@trait('mssql')
@trait('unit')
def expected_mapping(field_name: str, dbtype: str) -> None:
    entity_spec = get_entity_spec(TypeMapperTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    actual = mapper.get_provider_type(field_name)
    assert actual == dbtype, f'expected "{dbtype}" for "{field_name}", got "{actual}"'
