# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from deev.translation import (  # type: ignore  # pylint: disable=import-error
    deunionize,
    to_pyobject,
    to_sqlobject
)
from punit import collections, fact, inlinedata, theory
from types import NoneType
from typing import Any, Mapping, Optional, Union, get_origin
from uuid import UUID


@theory
@inlinedata(Optional[int], int)
@inlinedata(Optional[str], str)
@inlinedata(Optional[float], float)
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
@inlinedata('{"foo":"bar"}', dict[str, str], {'foo':'bar'})
@inlinedata('["foo","bar"]', tuple[str, ...], ('foo','bar'))
@inlinedata('["foo","bar"]', tuple, ('foo','bar'))
@inlinedata('"tuple`[\\"foo\\",\\"bar\\"]"', tuple[str, ...], ('foo','bar'))
@inlinedata('["foo","bar"]', list[str], ['foo','bar'])
@inlinedata('["foo","bar"]', list, ['foo','bar'])
@inlinedata('["foo","bar"]', set[str], {'foo','bar'})
@inlinedata('"set`[\\"foo\\",\\"bar\\"]"', set[str], {'foo','bar'})
@inlinedata('2023-05-19T21:43:46.539436+00:00', datetime, datetime(2023, 5, 19, 21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata('21:43:46.539436+00:00', time, time(21, 43, 46, 539436, tzinfo=timezone.utc))
@inlinedata(266583000321, timedelta, timedelta(days=3, seconds=7383, microseconds=321))
@inlinedata('2023-05-19', date, date(2023, 5, 19))
@inlinedata('04c182b78c784285b913c8981b4727bf', UUID, UUID('04c182b78c784285b913c8981b4727bf'))
@inlinedata("Decimal('123')", Decimal, Decimal(123))
@inlinedata('123', Decimal, Decimal(123))
@inlinedata(123, Decimal, Decimal(123))
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

@theory
@inlinedata(None, None, None)
@inlinedata(NoneType, None, None)
@inlinedata('null', None, None)
@inlinedata('NULL', None, None)
@inlinedata(123, int, 123)
@inlinedata(12.3, float, 12.3)
@inlinedata(True, bool, 1)
@inlinedata(False, bool, 0)
@inlinedata({'foo':'bar'}, dict[str, str], '{"foo":"bar"}')
@inlinedata(('foo','bar'), tuple[str, ...], '"tuple`[\\"foo\\",\\"bar\\"]"')
@inlinedata(['foo','bar'], list[str], '["foo","bar"]')
@inlinedata({'foo','bar'}, set[str], '"set`[\\"foo\\",\\"bar\\"]"')
@inlinedata(datetime(2023, 5, 19, 21, 43, 46, 539436), datetime,'2023-05-19T21:43:46.539436+00:00')
@inlinedata(time(21, 43, 46, 539436), time, '21:43:46.539436+00:00')
@inlinedata(timedelta(days=3, seconds=7383, microseconds=321), timedelta, 266583000321)
@inlinedata(date(2023, 5, 19), date, '2023-05-19')
@inlinedata(UUID('04c182b78c784285b913c8981b4727bf'), UUID, '04c182b78c784285b913c8981b4727bf')
@inlinedata(Decimal(123), Decimal, Decimal(123))
def to_sqlobject_bvt(value: Any, hint: type, expected: Any) -> None:
    actual = to_sqlobject(value, hint)
    if get_origin(hint) in (Mapping, dict, list, set, tuple):
        assert collections.areSame(actual, expected, sort=True), f'when collection value "{value}" and hint "{hint}", expected "{expected}" got "{actual}".'
    else:
        assert actual == expected, f'when scalar value "{value}" and hint "{hint}", expected "{expected}" got "{actual}".'
