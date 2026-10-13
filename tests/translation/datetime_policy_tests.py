# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from deev.entities import entity, field  # type: ignore  # pylint: disable=import-error
from deev.translation import (  # type: ignore  # pylint: disable=import-error
    MSSQL_DATETIME_TYPE_CONFIG_KEY,
    get_mssql_datetime_type,
    hydrate,
    splat,
    to_bsonobject,
    to_chsql_object,
    to_mssql_object,
    to_mysql_object,
    to_pyobject,
    to_sqlobject,
)
from deev.translation import datetime_utils  # type: ignore  # pylint: disable=import-error
from deev.translation.datetime_utils import (  # type: ignore  # pylint: disable=import-error
    __read_mssql_datetime_type,
    assume_utc,
    ensure_utc_aware,
)
from deev.translation.utils import (  # type: ignore  # pylint: disable=import-error
    __from_json,
    __to_json,
)
from punit import fact, inlinedata, theory  # type: ignore  # pylint: disable=import-error


@fact
def ensure_utc_aware_passthrough_aware() -> None:
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    assert ensure_utc_aware(dt) is dt


@fact
def ensure_utc_aware_tags_naive_as_utc() -> None:
    dt = datetime(2024, 1, 15, 12, 0, 0)
    assert ensure_utc_aware(dt) == datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@fact
def assume_utc_treats_naive_as_utc() -> None:
    assert assume_utc(datetime(2024, 1, 15, 12, 0, 0)) == datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@fact
def assume_utc_normalizes_aware() -> None:
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    assert assume_utc(dt) == datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)


@fact
def get_mssql_datetime_type_defaults_to_datetimeoffset() -> None:
    old = os.environ.get(MSSQL_DATETIME_TYPE_CONFIG_KEY)
    os.environ.pop(MSSQL_DATETIME_TYPE_CONFIG_KEY, None)
    try:
        assert __read_mssql_datetime_type() == 'DATETIMEOFFSET'
    finally:
        if old is None:
            os.environ.pop(MSSQL_DATETIME_TYPE_CONFIG_KEY, None)
        else:
            os.environ[MSSQL_DATETIME_TYPE_CONFIG_KEY] = old


@fact
def get_mssql_datetime_type_reads_configured_value_verbatim() -> None:
    for value in ('DATETIME2', 'DATETIME2(6)', 'datetimeoffset', 'WHATEVER'):
        old = os.environ.get(MSSQL_DATETIME_TYPE_CONFIG_KEY)
        os.environ[MSSQL_DATETIME_TYPE_CONFIG_KEY] = value
        try:
            assert __read_mssql_datetime_type() == value, 'the configured value must be used verbatim'
        finally:
            if old is None:
                os.environ.pop(MSSQL_DATETIME_TYPE_CONFIG_KEY, None)
            else:
                os.environ[MSSQL_DATETIME_TYPE_CONFIG_KEY] = old


@fact
def naive_datetime_is_always_treated_as_utc() -> None:
    naive = datetime(2024, 1, 15, 12, 0, 0)
    expected = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    old = datetime_utils.__mssql_datetime_type
    datetime_utils.__mssql_datetime_type = 'DATETIMEOFFSET'
    try:
        assert to_sqlobject(naive, datetime) == expected
        assert to_mssql_object(naive, datetime) == expected
    finally:
        datetime_utils.__mssql_datetime_type = old
    datetime_utils.__mssql_datetime_type = 'DATETIME2'
    try:
        assert to_mssql_object(naive, datetime) == expected
    finally:
        datetime_utils.__mssql_datetime_type = old
    for convert in (to_mysql_object, to_chsql_object, to_bsonobject):
        assert convert(naive, datetime) == expected, f'{convert.__name__} did not treat naive values as UTC'
    assert to_pyobject(naive, datetime, from_sql=True) == expected
    assert to_pyobject(naive, datetime, from_mssql=True) == expected
    assert to_pyobject(naive, datetime, from_mysql=True) == expected
    assert to_pyobject(naive, datetime, from_chsql=True) == expected
    assert to_pyobject(naive, datetime, from_bson=True) == expected
    assert to_pyobject(naive, datetime) == expected
    assert __to_json(naive) == __to_json(expected)


@fact
def write_policies_offset_storing_backends() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    naive = datetime(2024, 1, 15, 12, 0, 0)
    expected_naive = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    old = datetime_utils.__mssql_datetime_type
    datetime_utils.__mssql_datetime_type = 'DATETIMEOFFSET'
    try:
        # SQLite and MSSQL (DATETIMEOFFSET) store offset information.
        assert to_sqlobject(aware, datetime) == aware
        assert to_mssql_object(aware, datetime) == aware
        assert to_sqlobject(naive, datetime) == expected_naive
        assert to_mssql_object(naive, datetime) == expected_naive
    finally:
        datetime_utils.__mssql_datetime_type = old


@fact
def write_policies_utc_storing_backends() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    naive = datetime(2024, 1, 15, 12, 0, 0)
    expected_aware = datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
    expected_naive = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    old = datetime_utils.__mssql_datetime_type
    datetime_utils.__mssql_datetime_type = 'DATETIME2'
    try:
        # MySQL, ClickHouse, MongoDB, and MSSQL (non-offset types) store UTC.
        for convert in (to_mysql_object, to_chsql_object, to_bsonobject, to_mssql_object):
            assert convert(aware, datetime) == expected_aware, f'{convert.__name__} did not normalize aware values to UTC'
            assert convert(naive, datetime) == expected_naive, f'{convert.__name__} did not treat naive values as UTC'
    finally:
        datetime_utils.__mssql_datetime_type = old


@fact
def mssql_default_type_preserves_offsets_and_tags_naive_utc() -> None:
    old = datetime_utils.__mssql_datetime_type
    datetime_utils.__mssql_datetime_type = 'DATETIMEOFFSET'
    try:
        aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
        naive = datetime(2024, 1, 15, 12, 0, 0)
        expected_naive = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert to_mssql_object(aware, datetime) == aware
        assert to_mssql_object(naive, datetime) == expected_naive
        assert to_pyobject(aware, datetime, from_mssql=True) == aware
        assert to_pyobject(naive, datetime, from_mssql=True) == expected_naive
    finally:
        datetime_utils.__mssql_datetime_type = old


@fact
def mssql_configured_type_normalizes_to_utc() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    naive = datetime(2024, 1, 15, 12, 0, 0)
    expected_aware = datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
    expected_naive = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    old = datetime_utils.__mssql_datetime_type
    datetime_utils.__mssql_datetime_type = 'DATETIME2'
    try:
        assert to_mssql_object(aware, datetime) == expected_aware
        assert to_mssql_object(naive, datetime) == expected_naive
        assert to_pyobject(aware, datetime, from_mssql=True) == expected_aware
        assert to_pyobject(naive, datetime, from_mssql=True) == expected_naive
    finally:
        datetime_utils.__mssql_datetime_type = old


@theory
@inlinedata('2024-01-15T12:00:00+05:00', datetime, 'from_sql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5))))
@inlinedata('2024-01-15T12:00:00+05:00', datetime, 'from_mssql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5))))
@inlinedata('2024-01-15T12:00:00+00:00', datetime, 'from_mysql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00+00:00', datetime, 'from_chsql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00+00:00', datetime, 'from_bson', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00+05:00', datetime, None, datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5))))
def read_policies_aware_strings(value: str, hint: type, flag: str | None, expected: datetime) -> None:
    kwargs = {flag: True} if flag is not None else {}
    assert to_pyobject(value, hint, **kwargs) == expected


@theory
@inlinedata('2024-01-15T12:00:00', datetime, 'from_sql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00', datetime, 'from_mssql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00', datetime, 'from_mysql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00', datetime, 'from_chsql', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00', datetime, 'from_bson', datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
@inlinedata('2024-01-15T12:00:00', datetime, None, datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
def read_policies_naive_strings(value: str, hint: type, flag: str | None, expected: datetime) -> None:
    kwargs = {flag: True} if flag is not None else {}
    assert to_pyobject(value, hint, **kwargs) == expected


@fact
def read_policies_aware_instances_defensively_normalized_for_utc_backends() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    expected = datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
    assert to_pyobject(aware, datetime, from_mysql=True) == expected
    assert to_pyobject(aware, datetime, from_chsql=True) == expected
    assert to_pyobject(aware, datetime, from_bson=True) == expected


@fact
def read_policies_aware_instances_preserved_elsewhere() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    old = datetime_utils.__mssql_datetime_type
    datetime_utils.__mssql_datetime_type = 'DATETIMEOFFSET'
    try:
        assert to_pyobject(aware, datetime, from_sql=True) == aware
        assert to_pyobject(aware, datetime, from_mssql=True) == aware
        assert to_pyobject(aware, datetime) == aware
    finally:
        datetime_utils.__mssql_datetime_type = old


@fact
def to_pyobject_rejects_multiple_flags() -> None:
    try:
        to_pyobject(datetime(2024, 1, 1), datetime, from_sql=True, from_mysql=True)
        assert False, 'expected ValueError for multiple provider flags'
    except ValueError:
        pass


@fact
def splat_rejects_multiple_flags() -> None:
    try:
        splat(object(), to_sql=True, to_mysql=True)
        assert False, 'expected ValueError for multiple destination flags'
    except ValueError:
        pass


@fact
def hydrate_rejects_multiple_flags() -> None:
    try:
        hydrate(object, {}, from_sql=True, from_mysql=True)
        assert False, 'expected ValueError for multiple source flags'
    except ValueError:
        pass


@fact
def splat_hydrate_mysql_roundtrip_normalizes_to_utc() -> None:
    @entity
    class MysqlBvt:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)

    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    expected = datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
    data = splat(MysqlBvt(id='1', ts=aware), to_mysql=True)
    assert data['ts'] == expected
    hydrated = hydrate(MysqlBvt, {'id': '1', 'ts': expected}, from_mysql=True)
    assert hydrated.ts == expected


@fact
def json_encoding_preserves_offsets() -> None:
    aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    json_str: str = __to_json(aware)
    assert '+05:00' in json_str, f'expected the offset to be preserved in {json_str}'
    assert __from_json(json_str) == aware


@fact
def json_encoding_uses_z_for_utc() -> None:
    utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    json_str: str = __to_json(utc_dt)
    assert 'Z' in json_str, f'expected Z-suffix for UTC in {json_str}'
    assert __from_json(json_str) == utc_dt


@fact
def json_encoding_treats_naive_as_utc() -> None:
    naive = datetime(2024, 1, 15, 12, 0, 0)
    expected = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    json_str: str = __to_json(naive)
    assert 'Z' in json_str, f'expected Z-suffix for UTC in {json_str}'
    assert __from_json(json_str) == expected


@fact
def json_encoding_applies_policy_to_containers() -> None:
    naive = datetime(2024, 1, 15, 12, 0, 0)
    expected = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    json_str: str = __to_json({'when': [naive, datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))]})
    parsed: Any = __from_json(json_str)
    assert parsed['when'][0] == expected
    assert parsed['when'][1] == datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
