# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from datetime import datetime


def __adapt_datetime(dt: datetime) -> str:
    return dt.isoformat(sep=' ')


def register_datetime_adapter() -> None:
    """
    Register deev's explicit ``sqlite3`` datetime adapter.

    Pins the storage format to ``datetime.isoformat(sep=' ')`` (timezone-aware
    values include their UTC offset) instead of relying on the stdlib default
    adapter, which is deprecated and slated for removal.  The registration is
    idempotent and process-wide.
    """
    sqlite3.register_adapter(datetime, __adapt_datetime)


__all__ = ['register_datetime_adapter']
