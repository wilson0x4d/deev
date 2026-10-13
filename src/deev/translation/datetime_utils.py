# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

"""Datetime timezone policy utilities shared by the translation layer.

deev guarantees that every ``datetime`` value that passes through its read and
write paths is timezone-aware.  Naive values are always interpreted as UTC
(tagged, never converted); timezone-aware values are preserved unchanged when
the store can carry the offset (SQLite, MSSQL ``DATETIMEOFFSET``, JSON) and
normalized to UTC otherwise (MySQL, ClickHouse, MongoDB, and MSSQL with any
other ``DEEV__MSSQL__DATETIME_TYPE``).
"""

from __future__ import annotations

from datetime import datetime, timezone

import appsettings2

MSSQL_DATETIME_TYPE_CONFIG_KEY = 'DEEV__MSSQL__DATETIME_TYPE'


def __read_mssql_datetime_type() -> str:
    """
    Read the configured MSSQL datetime type from configuration.

    The value is used verbatim (no validation, no normalization); the default
    is ``DATETIMEOFFSET`` when the key is absent.
    """
    return appsettings2.get_configuration().get(MSSQL_DATETIME_TYPE_CONFIG_KEY, default='DATETIMEOFFSET')


__mssql_datetime_type: str = __read_mssql_datetime_type()


def get_mssql_datetime_type() -> str:
    """
    Return the configured MSSQL datetime storage type.

    The ``DEEV__MSSQL__DATETIME_TYPE`` configuration value is used verbatim
    (no validation, no normalization); the default is ``DATETIMEOFFSET``.
    The value is populated from configuration once when this module is
    loaded, and that initial population serves as the cache for the
    lifetime of the process.

    :return: The MSSQL datetime type (e.g. ``DATETIMEOFFSET``, ``DATETIME2``, ``DATETIME2(6)``).
    """
    return __mssql_datetime_type


def ensure_utc_aware(dt: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware, treating naive values as UTC.

    Timezone-aware values are returned unchanged; naive values have UTC
    applied via ``replace`` (no change to the instant).  This is the deev
    policy, on both reads and writes, for stores that can carry the offset
    (SQLite, MSSQL ``DATETIMEOFFSET``, and the provider-agnostic JSON path):
    rows written by deev always carry an explicit offset (UTC for rows
    written by any deev version), so a naive value is assumed to already be
    UTC.

    :param dt: The datetime to normalize.
    :return: A timezone-aware datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def assume_utc(dt: datetime) -> datetime:
    """
    Normalize a datetime to aware UTC.

    Naive values are tagged UTC via ``replace`` (no change to the instant);
    timezone-aware values are converted via ``astimezone``.  This is the
    deev policy, on both reads and writes, for stores that cannot carry the
    offset (MySQL, ClickHouse, MongoDB, and MSSQL with any type other than
    ``DATETIMEOFFSET``), which store UTC.

    :param dt: The datetime to normalize.
    :return: A UTC-aware datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


__all__ = [
    'MSSQL_DATETIME_TYPE_CONFIG_KEY',
    'assume_utc',
    'ensure_utc_aware',
    'get_mssql_datetime_type',
]
