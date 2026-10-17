# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import datetime, time, timezone
from decimal import Decimal
from deev import entity, field
from deev.entities import get_entity_spec
from deev.mssql import MSSQLTypeMapper
from deev.mssql.mssql_input_sizes import input_sizes, resolve_where_fields
from punit import fact, theory, inlinedata, trait
from typing import Any, Callable
from uuid import UUID, uuid4

from mssql_python.constants import ConstantsDDBC as C


@entity
class InputSizesTestEntity:
    s_max: str = field(max=50)
    big: int | None = field(dbtype='BIGINT')
    with_varchar: str | None = field(dbtype='VARCHAR(42)')
    id: int = field(autoincrement=True, primary_key=True, default=0)
    s_plain: str | None = None
    s_json: dict[str, Any] | None = None
    n: int | None = None
    b: bool | None = None
    f: float | None = None
    d: Decimal | None = None
    dt: datetime | None = None
    uid: UUID | None = None
    t: time | None = None
    unmappable: Callable | None = None


def __sizes_for(field_name: str, *values: Any) -> Any:
    entity_spec = get_entity_spec(InputSizesTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    return input_sizes(entity_spec, mapper, [field_name], [values])


@fact
@trait('mssql')
@trait('unit')
def string_uses_field_max_when_value_is_shorter() -> None:
    # NVARCHAR(50) column, 3-char value -> declared at the column size
    assert __sizes_for('s_max', 'abc') == [(C.SQL_WVARCHAR.value, 50, 0)]


@fact
@trait('mssql')
@trait('unit')
def string_uses_value_length_when_value_is_longer() -> None:
    # declared size must never be smaller than the value (driver truncation)
    assert __sizes_for('s_max', 'x' * 60) == [(C.SQL_WVARCHAR.value, 60, 0)]


@fact
@trait('mssql')
@trait('unit')
def string_without_max_defaults_from_data_type() -> None:
    # default str mapping is NVARCHAR(20)
    assert __sizes_for('s_plain', 'abc') == [(C.SQL_WVARCHAR.value, 20, 0)]


@fact
@trait('mssql')
@trait('unit')
def long_string_binds_as_max() -> None:
    # sizes beyond the inline limit are declared as 0 (NVARCHAR(MAX))
    assert __sizes_for('s_plain', 'x' * 5000) == [(C.SQL_WVARCHAR.value, 0, 0)]


@fact
@trait('mssql')
@trait('unit')
def unicode_string_uses_utf16_length() -> None:
    # astral characters consume two UTF-16 code units
    value = '\U0001F600' * 30  # 60 code units
    assert __sizes_for('s_plain', value) == [(C.SQL_WVARCHAR.value, 60, 0)]


@fact
@trait('mssql')
@trait('unit')
def json_field_uses_value_size() -> None:
    # NVARCHAR(MAX) column, size inferred from the value
    assert __sizes_for('s_json', '{"a":1}') == [(C.SQL_WVARCHAR.value, 7, 0)]


@fact
@trait('mssql')
@trait('unit')
def int_field_declares_column_type() -> None:
    assert __sizes_for('n', 5) == [(C.SQL_INTEGER.value, 10, 0)]
    assert __sizes_for('big', 5) == [(C.SQL_BIGINT.value, 19, 0)]


@fact
@trait('mssql')
@trait('unit')
def bool_field_declares_bit() -> None:
    assert __sizes_for('b', True) == [(C.SQL_BIT.value, 1, 0)]


@fact
@trait('mssql')
@trait('unit')
def float_field_declares_double() -> None:
    assert __sizes_for('f', 1.5) == [(C.SQL_DOUBLE.value, 15, 0)]


@fact
@trait('mssql')
@trait('unit')
def decimal_field_declares_precision_scale() -> None:
    assert __sizes_for('d', Decimal('1.25')) == [(C.SQL_NUMERIC.value, 20, 10)]


@fact
@trait('mssql')
@trait('unit')
def datetime_declares_by_timezone_awareness() -> None:
    aware = datetime.now(tz=timezone.utc)
    assert __sizes_for('dt', aware) == [(C.SQL_DATETIMEOFFSET.value, 34, 7)]
    assert __sizes_for('dt', datetime(2026, 1, 2, 3, 4, 5)) == [(C.SQL_TYPE_TIMESTAMP.value, 26, 6)]


@fact
@trait('mssql')
@trait('unit')
def uuid_as_string_declares_guid_representation() -> None:
    # deev transmits UUIDs as hyphenated strings; the server converts
    assert __sizes_for('uid', str(uuid4())) == [(C.SQL_WVARCHAR.value, 36, 0)]


@fact
@trait('mssql')
@trait('unit')
def uuid_object_falls_back_to_driver() -> None:
    # the driver natively converts UUID objects; no declaration
    assert __sizes_for('uid', uuid4()) is None


@fact
@trait('mssql')
@trait('unit')
def time_value_falls_back_to_driver() -> None:
    # the driver's text binding preserves full precision
    assert __sizes_for('t', time(1, 2, 3)) is None


@fact
@trait('mssql')
@trait('unit')
def varchar_column_with_ascii_value() -> None:
    assert __sizes_for('with_varchar', 'abc') == [(C.SQL_VARCHAR.value, 42, 0)]


@fact
@trait('mssql')
@trait('unit')
def varchar_column_with_unicode_value_falls_back() -> None:
    assert __sizes_for('with_varchar', '\u00e9') is None


@fact
@trait('mssql')
@trait('unit')
def null_value_declares_string() -> None:
    assert __sizes_for('s_max', None) == [(C.SQL_WVARCHAR.value, 50, 0)]
    assert __sizes_for('n', None) == [(C.SQL_WVARCHAR.value, 0, 0)]


@fact
@trait('mssql')
@trait('unit')
def null_and_value_share_column_declaration() -> None:
    entity_spec = get_entity_spec(InputSizesTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    assert input_sizes(entity_spec, mapper, ['n'], [(None,), (5,)]) == [(C.SQL_INTEGER.value, 10, 0)]
    assert input_sizes(entity_spec, mapper, ['s_max'], [(None,), ('x' * 60,)]) == [(C.SQL_WVARCHAR.value, 60, 0)]


@fact
@trait('mssql')
@trait('unit')
def multi_row_string_takes_max_size() -> None:
    entity_spec = get_entity_spec(InputSizesTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    assert input_sizes(entity_spec, mapper, ['s_max'], [('abc',), ('x' * 60,)]) == [(C.SQL_WVARCHAR.value, 60, 0)]


@fact
@trait('mssql')
@trait('unit')
def unknown_field_falls_back() -> None:
    entity_spec = get_entity_spec(InputSizesTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    assert input_sizes(entity_spec, mapper, ['nonexistent'], [(1,)]) is None


@fact
@trait('mssql')
@trait('unit')
def unmappable_field_falls_back() -> None:
    entity_spec = get_entity_spec(InputSizesTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    assert input_sizes(entity_spec, mapper, ['unmappable'], [(1,)]) is None


@fact
@trait('mssql')
@trait('unit')
def mixed_value_types_fall_back() -> None:
    entity_spec = get_entity_spec(InputSizesTestEntity)
    mapper = MSSQLTypeMapper(entity_spec)
    assert input_sizes(entity_spec, mapper, ['n'], [(1,), ('one',)]) is None


@theory
@inlinedata('a=?', 'a')
@inlinedata('a = ?', 'a')
@inlinedata('[a]=? AND [b]=?', 'a,b')
@inlinedata('a IN (?, ?)', 'a,a')
@inlinedata('a = ? AND UPPER(b) = ?', 'a,b')
@inlinedata('a = %? AND b = %?', 'a,b')
@inlinedata('A = ? AND B = ?', 'a,b')
@inlinedata("a = 'x?y'", '')
@inlinedata('a = ?', 'a')
@trait('mssql')
@trait('unit')
def where_clauses_resolve_to_fields(where: str, expected: str) -> None:
    resolved = resolve_where_fields(where, ['a', 'b', 'c'])
    expected_list = expected.split(',') if expected else []
    assert resolved == expected_list


@fact
@trait('mssql')
@trait('unit')
def unresolvable_placeholders_return_none() -> None:
    assert resolve_where_fields('?=a', ['a', 'b']) == [None]
    assert resolve_where_fields('a = (SELECT MAX(x) FROM other WHERE c = ?)', ['a']) == [None]
    assert resolve_where_fields('DATEADD(day, 1, a) = ?', ['a']) == ['a']
    assert resolve_where_fields('a > ? AND a < ?', ['a']) == ['a', 'a']
