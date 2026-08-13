# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum

from deev.translation import (  # type: ignore  # pylint: disable=import-error
    deunionize,
    to_pyobject,
    to_sqlobject
)
from deev.translation.utils import (  # type: ignore  # pylint: disable=import-error
    _to_json_value,
)
from punit import collections, fact, inlinedata, theory
from types import NoneType
from typing import Any, Mapping, Optional, Union, get_origin, AnyStr
from uuid import UUID


class Status(Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'


class NumericStatus(Enum):
    ACTIVE = 1
    INACTIVE = 2


class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@theory
@inlinedata(int | None, int)
@inlinedata(str | None, str)
@inlinedata(float | None, float)
@inlinedata(Union[int | str], int)
def can_deunionize_types(input: type, expected: type) -> None:
    actual = deunionize(input)
    assert actual is expected


@theory
@inlinedata(None, None, None)
@inlinedata(NoneType, None, None)
@inlinedata('null', None, None)
@inlinedata('NULL', None, None)
@inlinedata('123', int, 123)
@inlinedata('12.3', float, 12.3)
@inlinedata('1', bool, True)
@inlinedata('0', bool, False)
@inlinedata(1, bool, True)
@inlinedata(0, bool, False)
@inlinedata('TRUE', bool, True)
@inlinedata('FALSE', bool, False)
@inlinedata('True', bool, True)
@inlinedata('False', bool, False)
@inlinedata('{"foo":"bar"}', dict[str, str], {'foo': 'bar'})
@inlinedata('["foo","bar"]', tuple[str, ...], ('foo', 'bar'))
@inlinedata('["foo","bar"]', tuple, ('foo', 'bar'))
@inlinedata('"t`[\\"foo\\",\\"bar\\"]"', tuple[str, ...], ('foo', 'bar'))
@inlinedata('["foo","bar"]', list[str], ['foo', 'bar'])
@inlinedata('["foo","bar"]', list, ['foo', 'bar'])
@inlinedata('["foo","bar"]', set[str], {'foo', 'bar'})
@inlinedata('"s`[\\"foo\\",\\"bar\\"]"', set[str], {'foo', 'bar'})
@inlinedata('2023-05-19T21:43:46.539436Z', datetime, datetime(2023, 5, 19, 21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata('2023-05-19T21:43:46.539436+00:00', datetime, datetime(2023, 5, 19, 21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata('21:43:46.539436Z', time, time(21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata('21:43:46.539436+00:00', time, time(21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata(266583000321, timedelta, timedelta(days=3, seconds=7383, microseconds=321))
@inlinedata('2023-05-19', date, date(2023, 5, 19))
@inlinedata('04c182b78c784285b913c8981b4727bf', UUID, UUID('04c182b78c784285b913c8981b4727bf'))
@inlinedata('123', Decimal, Decimal(123))
@inlinedata(123, Decimal, Decimal(123))
@inlinedata('active', Status, Status.ACTIVE)
@inlinedata('inactive', Status, Status.INACTIVE)
@inlinedata(1, NumericStatus, NumericStatus.ACTIVE)
@inlinedata(2, NumericStatus, NumericStatus.INACTIVE)
@inlinedata(1, Priority, Priority.LOW)
@inlinedata(3, Priority, Priority.HIGH)
def to_pyobject_bvt(value: Any, hint: type, expected: Any) -> None:
    # assert compaitble conversion
    actual = to_pyobject(value, hint)
    if get_origin(hint) in (Mapping, dict, list, set, tuple):
        assert collections.areSame(actual, expected, sort=True), f'when collection value "{value}" and hint "{hint}", expected "{expected}" got "{actual}".'
    else:
        assert actual == expected, f'when scalar value "{value}" and hint "{hint}", expected "{expected}" got "{actual}".'
    # assert compatible typing
    if actual is not None:
        org = get_origin(hint)
        if org is None:
            assert isinstance(actual, hint), f'when type checking hint value "{value}" and hint "{hint}", expected "{hint}" got "{actual}".'
        else:
            assert isinstance(actual, org), f'when type checking org value "{value}" and hint "{hint}", expected "{org}" got "{actual}".'


@fact
def to_pyobject_non_class_hint_no_crash() -> None:
    result = to_pyobject('some_value', Optional[str])  # type: ignore[arg-type]
    assert result == 'some_value'

    result = to_pyobject('some_value', 'Status')  # type: ignore[arg-type]
    assert result == 'some_value'

    result = to_pyobject('some_value', Any)  # type: ignore[arg-type]
    assert result == 'some_value'


@theory
@inlinedata(None, None, None)
@inlinedata(NoneType, None, None)
@inlinedata('null', None, None)
@inlinedata('NULL', None, None)
@inlinedata(123, int, 123)
@inlinedata(12.3, float, 12.3)
@inlinedata(True, bool, 1)
@inlinedata(False, bool, 0)
@inlinedata({'foo': 'bar'}, dict[str, str], '{"foo":"bar"}')
@inlinedata(('foo', 'bar'), tuple[str, ...], '"t`[\\"foo\\",\\"bar\\"]"')
@inlinedata(['foo', 'bar'], list[str], '["foo","bar"]')
@inlinedata({'foo', 'bar'}, set[str], '"s`[\\"foo\\",\\"bar\\"]"')
@inlinedata(datetime(2023, 5, 19, 21, 43, 46, 539436, tzinfo=timezone.utc), datetime, '2023-05-19T21:43:46.539436Z')
@inlinedata(time(21, 43, 46, 539436, tzinfo=timezone.utc), time, '21:43:46.539436Z')
@inlinedata(timedelta(days=3, seconds=7383, microseconds=321), timedelta, 266583000321)
@inlinedata(date(2023, 5, 19), date, '2023-05-19')
@inlinedata(UUID('04c182b78c784285b913c8981b4727bf'), UUID, '04c182b78c784285b913c8981b4727bf')
@inlinedata(Decimal(123), Decimal, Decimal(123))
@inlinedata(Status.ACTIVE, Status, 'active')
@inlinedata(Status.INACTIVE, Status, 'inactive')
@inlinedata(NumericStatus.ACTIVE, NumericStatus, 1)
@inlinedata(NumericStatus.INACTIVE, NumericStatus, 2)
@inlinedata(Priority.LOW, Priority, 1)
@inlinedata(Priority.HIGH, Priority, 3)
def to_sqlobject_bvt(value: Any, hint: type, expected: Any) -> None:
    actual = to_sqlobject(value, hint)
    if get_origin(hint) in (Mapping, dict, list, set, tuple):
        assert collections.areSame(actual, expected, sort=True), f'when collection value "{value}" and hint "{hint}", expected "{expected}" got "{actual}".'
    else:
        assert actual == expected, f'when scalar value "{value}" and hint "{hint}", expected "{expected}" got "{actual}".'
