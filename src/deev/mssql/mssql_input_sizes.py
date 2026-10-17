# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

"""
Compute input-size declarations for ``mssql_python`` parameters.

``mssql_python`` sizes string parameters from the Python value itself
(``len(value)``).  When a value is longer than the target column this
produces "String data, right truncation" failures — even in ``WHERE``
comparisons that should simply return no rows — and it makes the
declared parameter shape depend on the data.  Declaring input sizes per
parameter before ``execute``/``executemany`` (via
:meth:`mssql_python.Cursor.setinputsizes`) supplies the driver with the
column's type/size information, taken from the entity/field spec
(``dbtype`` or ``max``) and falling back to a default inferred from the
Python data type when the spec carries no length information.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

from mssql_python.constants import ConstantsDDBC as C

from ..common.db_error import DbError
from ..entities import EntitySpec
from .mssql_type_mapper import MSSQLTypeMapper

SqlInputSize = tuple[int, int, int]
"""A ``(sql_type, column_size, decimal_digits)`` triple for ``setinputsizes``."""

# NVARCHAR/VARCHAR inline limit; larger declared sizes are invalid, bind as MAX (0)
_MAX_INLINE_STRING_SIZE = 4000

_SQL_TYPE_RE = re.compile(
    r'^\s*(?P<name>[A-Za-z]+)\s*(?:\(\s*(?P<arg1>\d+)(?:\s*,\s*(?P<arg2>\d+))?\s*\)|\(\s*MAX\s*\))?\s*$',
    re.IGNORECASE,
)

# sql server type name -> (odbc sql type, default column size, default decimal digits)
#
# The default column size only applies when the type carries no length
# argument (a bare ``dbtype`` override, since generated DDL always emits
# ``TYPE(n)`` or ``TYPE(MAX)``).  For variable-length types ``0`` means
# MAX — the honest "no length information" fallback and the driver's own
# long-data sentinel.  Fixed-length types have no MAX form, so ``1`` (the
# minimum legal length) stands in; ``_effective_string_size`` still floors
# the declaration at the value's actual length in all cases.
_SQL_TYPE_MAP: dict[str, tuple[int, int, int]] = {
    'BIT': (C.SQL_BIT.value, 1, 0),
    'TINYINT': (C.SQL_TINYINT.value, 3, 0),
    'SMALLINT': (C.SQL_SMALLINT.value, 5, 0),
    'INT': (C.SQL_INTEGER.value, 10, 0),
    'INTEGER': (C.SQL_INTEGER.value, 10, 0),
    'BIGINT': (C.SQL_BIGINT.value, 19, 0),
    'REAL': (C.SQL_REAL.value, 7, 0),
    'FLOAT': (C.SQL_DOUBLE.value, 15, 0),
    'DECIMAL': (C.SQL_NUMERIC.value, 18, 0),
    'NUMERIC': (C.SQL_NUMERIC.value, 18, 0),
    'CHAR': (C.SQL_CHAR.value, 1, 0),
    'NCHAR': (C.SQL_WCHAR.value, 1, 0),
    'VARCHAR': (C.SQL_VARCHAR.value, 0, 0),
    'NVARCHAR': (C.SQL_WVARCHAR.value, 0, 0),
    'TEXT': (C.SQL_VARCHAR.value, 0, 0),
    'NTEXT': (C.SQL_WVARCHAR.value, 0, 0),
    'DATE': (C.SQL_TYPE_DATE.value, 10, 0),
    'TIME': (C.SQL_TYPE_TIME.value, 16, 7),
    'DATETIME': (C.SQL_TYPE_TIMESTAMP.value, 26, 3),
    'DATETIME2': (C.SQL_SS_TIME2.value, 26, 7),
    'DATETIMEOFFSET': (C.SQL_DATETIMEOFFSET.value, 34, 7),
    'UNIQUEIDENTIFIER': (C.SQL_GUID.value, 16, 0),
    'BINARY': (C.SQL_BINARY.value, 1, 0),
    'VARBINARY': (C.SQL_VARBINARY.value, 1, 0),
    'IMAGE': (C.SQL_VARBINARY.value, 0, 0),
    'XML': (C.SQL_SS_XML.value, 0, 0),
}

_STRING_TYPE_NAMES = frozenset({'CHAR', 'NCHAR', 'VARCHAR', 'NVARCHAR', 'TEXT', 'NTEXT'})
_NON_UNICODE_STRING_NAMES = frozenset({'CHAR', 'VARCHAR', 'TEXT'})
# column types whose values deev transmits as strings, with default representation sizes
_STRING_VALUE_TYPE_SIZES = {'DATE': 10, 'TIME': 16, 'UNIQUEIDENTIFIER': 36, 'XML': 0}
_INT_TYPE_NAMES = frozenset({'TINYINT', 'SMALLINT', 'INT', 'INTEGER', 'BIGINT'})
_BINARY_TYPE_NAMES = frozenset({'BINARY', 'VARBINARY', 'IMAGE'})

_WHERE_TOKEN_RE = re.compile(
    r"""'(?:[^']|'')*'|"(?:[^"]|"")*"|\[[^\]]*\]|\b[A-Za-z_][A-Za-z0-9_]*\b|\?"""
)
_SQL_KEYWORDS = frozenset({
    'all', 'and', 'any', 'as', 'asc', 'between', 'by', 'case', 'cast', 'commit',
    'convert', 'cross', 'current_timestamp', 'dense_rank', 'desc', 'distinct',
    'else', 'end', 'except', 'exists', 'fetch', 'full', 'getdate', 'getutcdate',
    'group', 'having', 'iif', 'identity', 'in', 'inner', 'insert', 'into', 'intersect',
    'is', 'isnull', 'join', 'left', 'like', 'newid', 'newsequentialid', 'next',
    'not', 'null', 'offset', 'on', 'or', 'outer', 'over', 'partition', 'rank',
    'recursive', 'right', 'rows', 'select', 'set', 'some', 'top', 'union',
    'unique', 'update', 'values', 'when', 'where', 'with'
})


def _parse_sql_type(sql_type: str) -> tuple[str, int | None, int | None] | None:
    """
    Parse a SQL Server column type into its name and arguments.

    :param sql_type: A SQL type string such as ``NVARCHAR(50)`` or ``DECIMAL(20,10)``.
    :returns: A ``(name, arg1, arg2)`` tuple (name upper-cased, ``MAX`` yields
      ``arg1 == 0``), or ``None`` when the string is not a recognizable type.
    """
    match = _SQL_TYPE_RE.match(sql_type)
    if match is None:
        return None
    name = match.group('name').upper()
    arg1 = int(match.group('arg1')) if match.group('arg1') is not None else None
    arg2 = int(match.group('arg2')) if match.group('arg2') is not None else None
    if re.search(r'\(\s*MAX\s*\)', sql_type, re.IGNORECASE) is not None:
        arg1 = 0
    return (name, arg1, arg2)


def _effective_string_size(column_size: int | None, value: str) -> int:
    """
    Compute the declared size for a string parameter.

    The declared size is the larger of the column size and the value's
    UTF-16 length.  Declaring a size smaller than the value truncates at
    the driver; declaring a size larger than the column is always safe
    (the server widens the column for comparisons).  Sizes beyond the
    inline limit are declared as ``0`` (``NVARCHAR(MAX)``).

    :param column_size: The column's declared size (``0``/``None`` for ``MAX``).
    :param value: The string value being bound.
    :returns: The declared column size.
    """
    size = column_size if column_size is not None else 0
    utf16_len = sum(2 if ord(ch) > 0xFFFF else 1 for ch in value)
    effective = max(size, utf16_len)
    if effective > _MAX_INLINE_STRING_SIZE:
        return 0  # 'MAX'
    return effective


def _is_ascii(value: str) -> bool:
    return all(ord(ch) <= 0x7F for ch in value)


def _binding_for(type_name: str, arg1: int | None, arg2: int | None, value: Any) -> SqlInputSize | None:
    """
    Compute the ODBC binding for a single non-NULL value against a column
    of the given SQL Server type.

    The SQL type is driven by the value's Python type (what the driver's
    C binder accepts) while the size/precision is driven by the column
    definition from the entity/field spec.

    :param type_name: Upper-cased SQL type name (e.g. ``NVARCHAR``).
    :param arg1: The type's first argument (size/precision), or ``None``.
    :param arg2: The type's second argument (scale), or ``None``.
    :param value: The Python value being bound (not ``None``).
    :returns: A ``(sql_type, column_size, decimal_digits)`` triple, or
      ``None`` when no safe declaration exists for this value/type pair
      (the caller falls back to the driver's native type detection).
    """
    base = _SQL_TYPE_MAP.get(type_name)
    if base is None:
        return None
    sql_type, default_size, default_digits = base

    if isinstance(value, str):
        if type_name in _STRING_TYPE_NAMES:
            # a non-unicode column cannot safely hold unicode values via a
            # char C-type binding; let the driver pick its native (wider) type
            if type_name in _NON_UNICODE_STRING_NAMES and not _is_ascii(value):
                return None
            return (sql_type, _effective_string_size(arg1 if arg1 is not None else default_size, value), 0)
        if type_name in _STRING_VALUE_TYPE_SIZES:
            # deev transmits date/time/UUID/JSON values as strings; the
            # server converts them to the column's type
            return (C.SQL_WVARCHAR.value, _effective_string_size(_STRING_VALUE_TYPE_SIZES[type_name], value), 0)
        # string against any other column type: declare a unicode string
        # sized from the value (mirrors the driver's native detection)
        return (C.SQL_WVARCHAR.value, _effective_string_size(0, value), 0)

    if isinstance(value, bool):
        return (C.SQL_BIT.value, 1, 0)

    if isinstance(value, int):
        if type_name == 'BIT':
            # the C_BIT binder rejects int values; the server converts 0/1
            return (C.SQL_INTEGER.value, 10, 0)
        if type_name in _INT_TYPE_NAMES:
            return (sql_type, arg1 if arg1 is not None else default_size, 0)
        return None

    if isinstance(value, float):
        if type_name in ('FLOAT', 'REAL'):
            return (sql_type, default_size, 0)
        return None

    if isinstance(value, Decimal):
        if type_name in ('DECIMAL', 'NUMERIC'):
            return (sql_type, arg1 if arg1 is not None else 18, arg2 if arg2 is not None else 0)
        return None

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return (C.SQL_DATETIMEOFFSET.value, 34, 7)
        return (C.SQL_TYPE_TIMESTAMP.value, 26, 6)

    if isinstance(value, date):
        return (C.SQL_TYPE_DATE.value, 10, 0)

    if isinstance(value, time):
        # the driver's native text binding preserves full precision; the
        # SQL_C_TYPE_TIME binding does not
        return None

    if isinstance(value, (bytes, bytearray)):
        if type_name in _BINARY_TYPE_NAMES:
            return (sql_type, arg1 if arg1 is not None else default_size, 0)
        return None

    if isinstance(value, UUID):
        # the driver natively converts UUID objects for GUID binding
        return None

    return None


def _all_null_binding(type_name: str, arg1: int | None) -> SqlInputSize:
    """
    Binding for a parameter position whose value is NULL in every row.

    NULL is declared as a unicode string; the server converts it to the
    column's type.  Universally safe across ODBC C-types.

    :param type_name: Upper-cased SQL type name of the column.
    :param arg1: The column's declared size/precision, or ``None``.
    :returns: A ``(sql_type, column_size, decimal_digits)`` triple.
    """
    size = arg1 if type_name in _STRING_TYPE_NAMES and arg1 is not None else 0
    return (C.SQL_WVARCHAR.value, size, 0)


def input_sizes(
    entity_spec: EntitySpec,
    type_mapper: MSSQLTypeMapper,
    field_names: Sequence[str],
    rows: Sequence[Sequence[Any]]
) -> list[SqlInputSize] | None:
    """
    Compute ``setinputsizes`` declarations for a set of parameters.

    The column type for each parameter is taken from the entity/field spec
    (``dbtype`` override, ``max`` for strings) with a default inferred
    from the field's Python data type.

    :param entity_spec: The entity specification.
    :param type_mapper: The provider type mapper (resolves the column's SQL type).
    :param field_names: The field name for each parameter, in parameter order.
    :param rows: One parameter row for ``execute``, or one row per batch for
      ``executemany`` (string sizes take the maximum across rows).
    :returns: A list of ``(sql_type, column_size, decimal_digits)`` triples, or
      ``None`` when any parameter cannot be safely declared.  Callers must skip
      ``setinputsizes`` entirely on ``None`` so the driver falls back to its
      native type detection.
    """
    if len(field_names) == 0 or len(rows) == 0:
        return None
    for row in rows:
        if len(row) != len(field_names):
            return None
    sizes: list[SqlInputSize] = []
    for idx, field_name in enumerate(field_names):
        if entity_spec.fields.get(field_name) is None:
            return None
        try:
            sql_type = type_mapper.get_provider_type(field_name)
        except DbError:
            return None
        parsed = _parse_sql_type(sql_type)
        if parsed is None or _SQL_TYPE_MAP.get(parsed[0]) is None:
            return None
        type_name, arg1, arg2 = parsed
        values = [row[idx] for row in rows]
        non_null = [v for v in values if v is not None]
        if len(non_null) == 0:
            sizes.append(_all_null_binding(type_name, arg1))
            continue
        anchor = _binding_for(type_name, arg1, arg2, non_null[0])
        if anchor is None:
            return None
        max_size = anchor[1]
        max_digits = anchor[2]
        for value in non_null[1:]:
            binding = _binding_for(type_name, arg1, arg2, value)
            if binding is None or binding[0] != anchor[0]:
                # mixed value types in one column position (e.g. a str
                # alongside an int for a numeric column) — fall back to
                # the driver's native detection for the whole statement
                return None
            max_size = max(max_size, binding[1])
            max_digits = max(max_digits, binding[2])
        sizes.append((anchor[0], max_size, max_digits))
    return sizes


def resolve_where_fields(where: str, field_names: Sequence[str]) -> list[str | None]:
    """
    Best-effort mapping of ``?`` placeholders in a WHERE clause to entity fields.

    For each ``?``, the nearest preceding identifier (skipping SQL keywords,
    string literals, and punctuation) is matched case-insensitively against
    the entity's field names.  Both ``?`` and deev's canonical ``%?``
    placeholder style are recognized.

    :param where: The WHERE clause (without the ``WHERE`` keyword).
    :param field_names: The entity's field names.
    :returns: A list with one entry per ``?`` — the matching field name, or
      ``None`` when the placeholder cannot be attributed to a field.
    """
    where = where.replace('%?', '?')
    field_map = {name.lower(): name for name in field_names}
    resolved: list[str | None] = []
    last_ident: str | None = None
    for match in _WHERE_TOKEN_RE.finditer(where):
        token = match.group(0)
        if token == '?':
            resolved.append(field_map.get(last_ident.lower()) if last_ident is not None else None)
        elif token.startswith(("'", '"')):
            continue
        elif token.startswith('['):
            last_ident = token[1:-1]
        elif token.lower() in _SQL_KEYWORDS:
            continue
        else:
            last_ident = token
    return resolved


__all__ = ['SqlInputSize', 'input_sizes', 'resolve_where_fields']
