# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Any

from deev.entities import entity, field, get_entity_spec
from deev.translation import compile_py_converter, compile_hydrate_plan, to_pyobject
from punit import fact, inlinedata, theory
from uuid import UUID, uuid4


class Color(Enum):
    RED = 'red'
    GREEN = 'green'


class Priority(IntEnum):
    LOW = 1
    HIGH = 3


__FLAG_COMBOS: tuple[dict[str, bool], ...] = (
    {},
    {'from_sql': True},
    {'from_mssql': True},
    {'from_bson': True},
    {'from_mysql': True},
    {'from_chsql': True},
)


@theory
@inlinedata(None, None)
@inlinedata(None, 'abc')
@inlinedata(None, 'null')
@inlinedata(None, 42)
@inlinedata(str, 'abc')
@inlinedata(str, 123)
@inlinedata(str, None)
@inlinedata(str, 'NULL')
@inlinedata(int, 123)
@inlinedata(int, '123')
@inlinedata(int, None)
@inlinedata(int, 'null')
@inlinedata(int, 1.5)
@inlinedata(float, 1.5)
@inlinedata(float, '1.5')
@inlinedata(float, None)
@inlinedata(float, 3)
@inlinedata(bool, 1)
@inlinedata(bool, 0)
@inlinedata(bool, '1')
@inlinedata(bool, 'TRUE')
@inlinedata(bool, 'true')
@inlinedata(bool, 'True')
@inlinedata(bool, '2')
@inlinedata(bool, 'nope')
@inlinedata(bool, True)
@inlinedata(bool, False)
@inlinedata(bool, None)
@inlinedata(bool, 'NULL')
@inlinedata(bool, 'null')
@inlinedata(UUID, uuid4())
@inlinedata(UUID, '04c182b7-8c78-4285-b913-c8981b4727bf')
@inlinedata(UUID, None)
@inlinedata(UUID, 'null')
@inlinedata(datetime, datetime(2023, 5, 19, 21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata(datetime, datetime(2023, 5, 19, 21, 43, 46))
@inlinedata(datetime, '2023-05-19T21:43:46.539436Z')
@inlinedata(datetime, '2023-05-19T21:43:46.539436+00:00')
@inlinedata(datetime, '2023-05-19T21:43:46')
@inlinedata(datetime, None)
@inlinedata(date, date(2023, 5, 19))
@inlinedata(date, datetime(2023, 5, 19, 12, 0, 0))
@inlinedata(date, '2023-05-19')
@inlinedata(date, None)
@inlinedata(time, time(21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata(time, time(21, 43, 46))
@inlinedata(time, '21:43:46.539436Z')
@inlinedata(time, '21:43:46.539436+05:00')
@inlinedata(time, None)
@inlinedata(timedelta, 266583000321)
@inlinedata(timedelta, timedelta(days=3))
@inlinedata(timedelta, 'x')
@inlinedata(timedelta, None)
@inlinedata(timedelta, True)
@inlinedata(timedelta, 0)
@inlinedata(Decimal, '123.45')
@inlinedata(Decimal, Decimal('123.45'))
@inlinedata(Decimal, 123)
@inlinedata(Decimal, None)
@inlinedata(Color, 'red')
@inlinedata(Color, Color.GREEN)
@inlinedata(Color, None)
@inlinedata(Color, 'null')
@inlinedata(Priority, 1)
@inlinedata(Priority, Priority.HIGH)
@inlinedata(Priority, None)
@inlinedata(list[int], [1, '2', 3])
@inlinedata(list[int], '[1, 2, 3]')
@inlinedata(list[int], [])
@inlinedata(list[int], None)
@inlinedata(list[int], (4, 5))
@inlinedata(list[int], 0.5)
@inlinedata(tuple, 5)
@inlinedata(set, 7)
@inlinedata(dict[str, int], 5)
@inlinedata(tuple[str, int], ('a', '1'))
@inlinedata(tuple, ('a', 'b'))
@inlinedata(tuple, None)
@inlinedata(tuple, '["a"]')
@inlinedata(set[str], {'a', 'b'})
@inlinedata(set, {'x', 'y'})
@inlinedata(set, None)
@inlinedata(dict[str, int], {'a': '1', 'b': 2})
@inlinedata(dict[str, str], {'a': 'b'})
@inlinedata(dict, {'a': 1})
@inlinedata(dict, None)
@inlinedata(dict, '{"a": 1}')
@inlinedata(list[datetime], ['2023-05-19T21:43:46Z'])
@inlinedata(dict[str, list[int]], {'a': ['1']})
@inlinedata(int | None, '123')
@inlinedata(int | None, None)
@inlinedata(int | None, 42)
@inlinedata(int | None, 'null')
@inlinedata(str | None, 'x')
@inlinedata(str | None, None)
def compiled_converter_matches_to_pyobject(hint: Any, value: Any) -> None:
    for flags in __FLAG_COMBOS:
        expected = to_pyobject(value, hint, **flags)
        actual = compile_py_converter(hint, **flags)(value)
        assert actual == expected, f'(hint={hint}, value={value!r}, flags={flags}, expected={expected!r}, actual={actual!r})'
        assert type(actual) is type(expected), f'(hint={hint}, value={value!r}, flags={flags}, expected type={type(expected)}, actual type={type(actual)})'


@fact
def compiled_converter_is_cached() -> None:
    assert compile_py_converter(int, from_sql=True) is compile_py_converter(int, from_sql=True), 'expected the same cached converter'
    assert compile_py_converter(int, from_sql=True) is not compile_py_converter(int, from_mssql=True), 'expected distinct converters for distinct flags'


@fact
def compiled_converter_handles_optional_hint() -> None:
    hint: Any = int | None
    convert = compile_py_converter(hint, from_sql=True)
    assert convert('123') == 123, f'expected 123, got {convert("123")}'
    assert convert(None) is None, f'expected None, got {convert(None)}'


@fact
def hydrate_plan_matches_field_order_and_marks_unmapped() -> None:
    @entity
    class PlanEntity:
        id: int = field(primary_key=True, default=0)
        name: str | None = None
        secret: str = field(default='s', mapped=False)
        tags: list[int] | None = None

    spec = get_entity_spec(PlanEntity)
    plan = compile_hydrate_plan(spec, from_sql=True)
    assert len(plan) == len(spec.fields), f'expected {len(spec.fields)} entries, got {len(plan)}'
    assert [name for name, _ in plan] == list(spec.fields.keys()), f'expected field order {list(spec.fields.keys())}, got {[name for name, _ in plan]}'
    converters = dict(plan)
    assert converters['secret'] is None, f'expected no converter for unmapped field, got {converters["secret"]}'
    assert all(callable(convert) for name, convert in plan if name != 'secret'), 'expected callable converters for mapped fields'


@fact
def hydrate_plan_converters_match_to_pyobject() -> None:
    @entity
    class PlanEntity:
        id: int = field(primary_key=True, default=0)
        ratio: float | None = None
        active: bool | None = None
        stamp: datetime | None = None
        tags: list[int] | None = None
        secret: str = field(default='s', mapped=False)

    spec = get_entity_spec(PlanEntity)
    plan = compile_hydrate_plan(spec, from_sql=True)
    values: tuple[Any, ...] = (None, '123', 0.5, '0.5', '1', '0', 'TRUE', 'nope', datetime(2024, 1, 2, tzinfo=timezone.utc), '2024-01-02T00:00:00Z', ['1', 2])
    for name, convert in plan:
        if convert is None:
            continue
        hint: Any = spec.attrs.get(name)
        for value in values:
            try:
                expected = to_pyobject(value, hint, from_sql=True)
                expected_error: type | None = None
            except Exception as e:
                expected, expected_error = None, type(e)
            try:
                actual = convert(value)
                actual_error: type | None = None
            except Exception as e:
                actual, actual_error = None, type(e)
            assert actual_error is expected_error, f'(field={name}, value={value!r}, expected error={expected_error}, actual error={actual_error})'
            if expected_error is None:
                assert actual == expected, f'(field={name}, value={value!r}, expected={expected!r}, actual={actual!r})'
