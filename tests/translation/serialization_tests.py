# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from deev.translation import (  # type: ignore  # pylint: disable=import-error
    __from_json,
    __to_json,
    to_pyobject,
)
from punit import collections, fact
from typing import Any
from uuid import UUID

@fact
def when_datetime() -> None:
    expected: datetime = datetime(2023, 4, 1, 12, 30, 45, 123456)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected, 'datetime round-trip failed'


@fact
def when_date() -> None:
    expected: date = date(2023, 4, 1)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected, 'date round-trip failed'


@fact
def when_time() -> None:
    expected: time = time(12, 30, 45, 123456)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected, 'time round-trip failed'


@fact
def when_decimal() -> None:
    expected: Decimal = Decimal('12345.6789')
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected, 'Decimal round-trip failed'


@fact
def when_uuid() -> None:
    expected: UUID = UUID('12345678-1234-5678-1234-567812345678')
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected, 'UUID round-trip failed'


@fact
def when_set() -> None:
    expected: set[int] = {1, 2, 3}
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    # ``set`` objects lose ordering; compare as sets.
    assert isinstance(actual, set), 'Decoded object is not a set'
    assert collections.areSame(actual, expected, sort=True), 'set round-trip failed'


@fact
def when_tuple() -> None:
    expected: tuple[int, ...] = (1, 2, 3)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert isinstance(actual, tuple), 'Decoded object is not a tuple'
    assert actual == expected, 'tuple round-trip failed'


@fact
def when_bytes() -> None:
    expected: bytes = b'\x00\xff\x7fHello'
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert isinstance(actual, bytes), 'Decoded object is not bytes'
    assert actual == expected, 'bytes round-trip failed'


@fact
def when_complex_structure() -> None:
    expected: dict[str, Any] = {
        'when': datetime(2023, 4, 1, 12, 30, 45, 123456),
        'day': date(2023, 4, 1),
        'moment': time(12, 30, 45, 123456),
        'price': Decimal('99.99'),
        'uid': UUID('12345678-1234-5678-1234-567812345678'),
        'tags': {'alpha', 'beta', 'gamma'},
        'coords': (1.0, 2.0, 3.0),
        'payload': b'\xde\xad\xbe\xef',
        'nested': {
            'list': [1, 2, 3],
            'set_in_list': [{1, 2}, {3, 4}],
        },
    }

    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)

    assert isinstance(actual, dict), 'Decoded top-level object is not a dict'
    assert actual['when'] == expected['when']
    assert actual['day'] == expected['day']
    assert actual['moment'] == expected['moment']
    assert actual['price'] == expected['price']
    assert actual['uid'] == expected['uid']
    assert isinstance(actual['tags'], set)
    assert collections.areSame(actual['tags'], expected['tags'], sort=True)
    assert isinstance(actual['coords'], tuple)
    assert actual['coords'] == expected['coords']
    assert isinstance(actual['payload'], bytes)
    assert actual['payload'] == expected['payload']
    # nested structures
    assert actual['nested']['list'] == expected['nested']['list']
    assert isinstance(actual['nested']['set_in_list'], list)
    for expected_set, actual_set in zip(
        expected['nested']['set_in_list'],
        actual['nested']['set_in_list'],
    ):
        assert isinstance(actual_set, set)
        assert actual_set == expected_set
