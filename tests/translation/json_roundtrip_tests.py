# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from deev.translation import (  # type: ignore  # pylint: disable=import-error
    to_pyobject,
    to_sqlobject,
)
from deev.translation.utils import (  # type: ignore  # pylint: disable=import-error
    __from_json,
    __to_json,
)
from punit import (  # type: ignore  # pylint: disable=import-error
    collections,
    fact,
    theory,
    inlinedata,
)
from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# JSON encoder/decoder round-trips (via __from_json for prefixed format)
# ---------------------------------------------------------------------------
@fact
def json_roundtrip_datetime_aware() -> None:
    expected: datetime = datetime(2023, 4, 1, 12, 30, 45, 123456, tzinfo=timezone.utc)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected, f'datetime round-trip failed: got {actual}'


@fact
def json_roundtrip_datetime_z_suffix() -> None:
    expected: datetime = datetime(2023, 11, 15, 8, 0, 0, tzinfo=timezone.utc)
    json_str: str = __to_json(expected)
    assert 'Z' in json_str, f'Expected Z-terminated in output, got {json_str}'
    actual: Any = __from_json(json_str)
    assert actual == expected


@fact
def json_roundtrip_datetime_with_microseconds() -> None:
    expected: datetime = datetime(2023, 6, 1, 0, 0, 0, 999999, tzinfo=timezone.utc)
    json_str: str = __to_json(expected)
    assert 'Z' in json_str
    assert '999999' in json_str
    actual: Any = __from_json(json_str)
    assert actual == expected


@fact
def json_roundtrip_datetime_no_microseconds() -> None:
    expected: datetime = datetime(2023, 6, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
    json_str: str = __to_json(expected)
    # Should not have a dot after T when microseconds are zero
    after_t = json_str.split('T')[1].rstrip('"') if 'T' in json_str else ''
    assert '.' not in after_t, f'datetime without microseconds should not have dot: {json_str}'
    assert 'Z' in json_str
    actual: Any = __from_json(json_str)
    assert actual == expected


@fact
def json_roundtrip_datetime_non_utc() -> None:
    tz = timezone(timedelta(hours=5))
    dt_val = datetime(2023, 7, 1, 10, 0, 0, tzinfo=tz)
    json_str: str = __to_json(dt_val)
    assert 'T05:00' in json_str, f'Expected UTC conversion, got {json_str}'
    assert 'Z' in json_str
    actual: Any = __from_json(json_str)
    assert actual == datetime(2023, 7, 1, 5, 0, 0, tzinfo=timezone.utc)


@fact
def json_roundtrip_date() -> None:
    expected: date = date(2023, 4, 1)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert actual == expected


@fact
def json_roundtrip_time_aware() -> None:
    expected: time = time(12, 30, 45, 123456, tzinfo=timezone.utc)
    json_str: str = __to_json(expected)
    assert 'Z' in json_str
    actual: Any = __from_json(json_str)
    assert actual.replace(tzinfo=None) == expected.replace(tzinfo=None)


@fact
def json_roundtrip_time_no_microseconds() -> None:
    expected: time = time(12, 0, 0, 0, tzinfo=timezone.utc)
    json_str: str = __to_json(expected)
    assert '.' not in json_str.rstrip('"')
    assert 'Z' in json_str
    actual: Any = __from_json(json_str)
    assert actual.replace(tzinfo=None) == expected.replace(tzinfo=None)


@fact
def json_roundtrip_decimal() -> None:
    expected: Decimal = Decimal('12345.6789')
    json_str: str = __to_json(expected)
    # Prefixed format: r'12345.6789'
    assert 'r`' in json_str
    actual: Any = __from_json(json_str)
    assert actual == expected, f'Decimal round-trip failed: got {actual}'


@fact
def json_roundtrip_decimal_via_pyobject() -> None:
    expected: Decimal = Decimal('12345.6789')
    # to_pyobject handles plain strings (non-prefixed) from JSON
    actual: Any = to_pyobject('12345.6789', Decimal)
    assert actual == expected


@fact
def json_roundtrip_decimal_various() -> None:
    for val in [Decimal('0'), Decimal('-1.5'), Decimal('1E+10'), Decimal('0.000'), Decimal('-0.00')]:
        json_str: str = __to_json(val)
        assert 'r`' in json_str
        actual: Any = __from_json(json_str)
        assert actual == val, f'Decimal round-trip failed for {val}: got {actual}'


@fact
def json_roundtrip_uuid() -> None:
    expected: UUID = UUID('12345678-1234-5678-1234-567812345678')
    json_str: str = __to_json(expected)
    # Prefixed format: u'canonical-uuid'
    assert 'u`' in json_str
    actual: Any = __from_json(json_str)
    assert actual == expected, f'UUID round-trip failed: got {actual}'


@fact
def json_roundtrip_set() -> None:
    expected: set[int] = {1, 2, 3}
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert isinstance(actual, set), 'Decoded object is not a set'
    assert collections.areSame(actual, expected, sort=True)


@fact
def json_roundtrip_tuple() -> None:
    expected: tuple[int, ...] = (1, 2, 3)
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert isinstance(actual, tuple), 'Decoded object is not a tuple'
    assert actual == expected


@fact
def json_roundtrip_bytes() -> None:
    expected: bytes = b'\x00\xff\x7fHello'
    json_str: str = __to_json(expected)
    actual: Any = __from_json(json_str)
    assert isinstance(actual, bytes), 'Decoded object is not bytes'
    assert actual == expected


@fact
def json_roundtrip_complex_nested() -> None:
    expected: dict[str, Any] = {
        'when': datetime(2023, 4, 1, 12, 30, 45, 123456, tzinfo=timezone.utc),
        'day': date(2023, 4, 1),
        'moment': time(12, 30, 45, 123456, tzinfo=timezone.utc),
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
    parsed: Any = __from_json(json_str)

    assert isinstance(parsed, dict)
    assert parsed['when'] == expected['when']
    assert parsed['day'] == expected['day']
    assert parsed['moment'].replace(tzinfo=None) == expected['moment'].replace(tzinfo=None)
    assert parsed['price'] == expected['price']
    assert parsed['uid'] == expected['uid']
    assert isinstance(parsed['tags'], set)
    assert collections.areSame(parsed['tags'], expected['tags'], sort=True)
    assert isinstance(parsed['coords'], tuple)
    assert parsed['coords'] == expected['coords']
    assert isinstance(parsed['payload'], bytes)
    assert parsed['payload'] == expected['payload']

    nested_sets = expected.get('nested', {}).get('set_in_list', [])
    parsed_sets = parsed.get('nested', {}).get('set_in_list', [])
    for es, ps in zip(nested_sets, parsed_sets):
        assert isinstance(ps, set)
        assert ps == es
