# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from typing import (
    Any,
)

from ..common.db_error import DbError


def parse_sql_where(where_clause: str | None, params: tuple[Any, ...]) -> dict[str, Any]:
    """Parse a SQL WHERE clause into a MongoDB filter dict.

    Supports = (equality), != / <> ($ne), < <= > >= ($lt, $lte, $gt, $gte),
    IN (list), IS NULL / IS NOT NULL, and positional %? placeholders.
    Conditions joined by AND are merged into a single flat dict
    (MongoDB treats dict keys as AND).  Conditions joined by OR produce
    an ``$or`` array in the top-level filter.
    This is a shared utility used by MongoProxyCursor.execute(),
    AsyncMongoProxyCursor.execute(), and MongoTableAdapter.query() to
    avoid code duplication.
    """
    if not where_clause:
        return {}
    param_idx = 0

    def _next_param() -> Any:
        nonlocal param_idx
        if param_idx >= len(params):
            raise DbError('WHERE clause has more placeholders than provided parameters.')
        val = params[param_idx]
        param_idx += 1
        return val

    def _resolve_value(value_str: str) -> Any:
        if value_str == '%?':
            return _next_param()
        lower = value_str.lower()
        if lower in ('true', 'false'):
            return lower == 'true'
        if value_str == 'NULL':
            return None
        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        try:
            return float(value_str) if '.' in value_str else int(value_str)
        except ValueError:
            raise DbError(f'Cannot parse WHERE value: {value_str}')

    def _parse_single_condition(token: str) -> tuple[str, Any]:
        null_match = re.match(
            r"([\w.]+)\s+IS\s+NOT\s+NULL", token, re.IGNORECASE
        )
        if null_match:
            return (null_match.group(1), {'$ne': None})
        null_match2 = re.match(r"([\w.]+)\s+IS\s+NULL", token, re.IGNORECASE)
        if null_match2:
            return (null_match2.group(1), {'$eq': None})
        in_match = re.match(r"([\w.]+)\s+IN\s*\((.+)\)", token, re.IGNORECASE)
        if in_match:
            field_name = in_match.group(1)
            inner = in_match.group(2)
            items = [it.strip() for it in inner.split(',')]
            return (field_name, {'$in': [_resolve_value(it) for it in items]})
        comp_match = re.match(
            r"([\w.]+)\s*(<=|>=|!=|<>|<|>|=)\s*(.+)", token, re.IGNORECASE
        )
        if comp_match:
            field_name, op_str, raw_val = comp_match.groups()
            val = _resolve_value(raw_val)
            upper_op = op_str.upper()
            mongo_op_map: dict[str, str] = {
                '!=': 'ne', '<>': 'ne',
                '<=': 'lte', '>=': 'gte',
                '<': 'lt', '>': 'gt',
                '=': '=',
            }
            if upper_op == '=':
                return (field_name, val)
            else:
                mongo_op = mongo_op_map.get(upper_op, None)
                if mongo_op is not None:
                    return (field_name, {f'${mongo_op}': val})
        raise DbError(f'Unrecognised WHERE condition: {token}')
    parts = re.split(r'\s+(AND|OR)\s+', where_clause, flags=re.IGNORECASE)
    or_groups: list[dict[str, Any]] = []
    and_group: dict[str, Any] = {}
    idx = 0
    while idx < len(parts):
        token = parts[idx].strip() if idx < len(parts) else ''
        idx += 1
        if not token:
            continue
        joiner = 'AND'
        if idx < len(parts):
            j = parts[idx].upper()
            if j in ('AND', 'OR'):
                joiner = j
                idx += 1
        try:
            field_name, mongo_value = _parse_single_condition(token)
        except DbError:
            if idx < len(parts) and parts[idx].upper() in ('AND', 'OR'):
                idx += 1
            continue
        if joiner == 'OR':
            and_group[field_name] = mongo_value
            or_groups.append(and_group)
            and_group = {}
        else:
            and_group[field_name] = mongo_value
    if not and_group and not or_groups:
        return {}
    if or_groups:
        or_groups.append(and_group)
        return {'$or': or_groups}
    return and_group


def infer_description_fields(value: Any) -> tuple[Any, int | None, int | None, int | None, int | None]:
    """Infer DB-API 2.0 description fields from a Python value.

    Per PEP 249, only name and type_code are mandatory; the remaining five
    are optional and should be None when no meaningful values can be provided.
    We return None for everything except display_size/internal_size (which we
    can derive from string byte length) and precision/scale (which we know
    for integer/float types).
    """
    if value is None:
        return None, None, None, None, None
    if isinstance(value, bool):
        return bool, None, None, None, None
    if isinstance(value, int):
        return int, len(str(abs(value))), 8, 38, 0
    if isinstance(value, float):
        return float, None, 8, 24, 16
    if isinstance(value, str):
        return str, len(value), len(value.encode()), None, None
    if isinstance(value, bytes):
        return bytes, None, len(value), None, None
    if isinstance(value, (dict, list, tuple, set)):
        text_repr = str(value)
        return str, len(text_repr), len(text_repr.encode()), None, None
    return str, None, None, None, None


__all__ = ['parse_sql_where', 'infer_description_fields']
