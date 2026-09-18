# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

"""
PEP 249 Database API 2.0 type definitions for cursor description.

Covers the 7-element tuple structure per the DB-API 2.0 spec.
"""

from enum import IntEnum
from typing import NamedTuple


class TypeCode(IntEnum):
    STRING = 1
    BINARY = 2
    NUMBER = 3
    DATETIME = 4
    ROWID = 5


class DescriptionField(NamedTuple):
    name: str
    type_code: TypeCode | type
    display_size: int | None
    internal_size: int | None
    precision: int | None
    scale: int | None
    null_ok: int


__all__ = [
    'DescriptionField',
    'TypeCode',
]
