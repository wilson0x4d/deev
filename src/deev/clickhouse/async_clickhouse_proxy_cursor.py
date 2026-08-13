# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Sequence
from uuid import UUID

import hanaro

from ..common.async_db_cursor import AsyncDbCursor
from ..common.db_params import DbParams

if TYPE_CHECKING:
    from clickhouse_connect.driver.asyncclient import AsyncClient


class AsyncClickHouseProxyCursor(AsyncDbCursor):
    """
    Normalized async cursor interface for clickhouse-connect AsyncClient.

    ClickHouse's async client does not follow the DB-API 2.0 cursor pattern.
    Instead it exposes ``query()``, ``command()``, and streaming methods directly
    on the client. This cursor wraps the AsyncClient to provide a DB-API 2.0
    compliant async cursor interface.

    Positional params (%?) are converted to pyformat %(pN)s format because
    ClickHouse's pyformat paramstyle is %(name)s.

    INSERT statements are routed through the native ``client.insert()``
    method for optimal performance.
    """

    __client: AsyncClient
    __cursor: logging.Logger
    __result: list[tuple[Any, ...]]
    __description: Sequence[tuple[Any, ...]] | None
    __rowcount: int
    __query_index: int
    __is_insert: bool
    __logger: logging.Logger

    def __init__(self, provider_client: AsyncClient, *args: Any, **kwargs: Any) -> None:
        self.__client = provider_client
        self.__cursor = hanaro.get_logger()
        self.__result = []
        self.__description = None
        self.__rowcount = 0
        self.__query_index = 0
        self.__is_insert = False

    @property
    def clickhouse_client(self) -> AsyncClient:
        """The underlying clickhouse_connect.driver.client.AsyncClient used by the cursor."""
        return self.__client

    @property
    def description(self) -> Sequence[tuple[Any, ...]] | None:
        return self.__description

    @property
    def rowcount(self) -> int:
        return self.__rowcount

    @property
    def summary(self) -> list[dict[str, Any]]:
        return getattr(self.__client, '_last_query_summary', []) or []  # type: ignore[attr-defined]

    @staticmethod
    def __get_pep249_type(clh_type_name: str) -> type:
        """Map a ClickHouse type name string to a Python type (PEP 249 type code)."""
        base = clh_type_name
        for wrapper in ('LowCardinality', 'Nullable'):
            if base.startswith(wrapper + '('):
                prefix = wrapper + '('
                base = base[len(prefix):-1]  # strip wrapper
        base = base.split('(')[0].split('[')[0].strip('\'"')
        base_lower = base.lower()
        if base_lower.startswith('nullable'):
            pass
        if base in ('Int8', 'Int16', 'Int32', 'Int64', 'Int128', 'Int256'):
            return int
        if base in ('UInt8', 'UInt16', 'UInt32', 'UInt64', 'UInt128', 'UInt256'):
            return int
        if base in ('Float32', 'Float64', 'BFloat16'):
            return float
        if base.startswith('Decimal'):
            return Decimal
        if base in ('String', 'FixedString', 'UUID', 'IPv4', 'IPv6', 'IPv6V4'):
            return str
        if base in ('Date', 'Date32'):
            return date
        if base in ('DateTime', 'DateTime64'):
            return datetime
        if base in ('Time', 'Time64'):
            return time
        if base in ('Bool', 'False', 'True'):
            return bool
        if base in ('Nothing', 'Null'):
            return type(None)
        if base in ('Map',):
            return dict
        if base in ('Array',):
            return list
        if base in ('Tuple',):
            return tuple
        if base in ('JSON',):
            return dict
        return str

    def __build_description(self, column_names: tuple[str, ...], column_types: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        """Build a PEP 249 compliant description from column_names and column_types."""
        description: list[tuple[Any, ...]] = []
        for name, ch_type in zip(column_names, column_types):
            type_name: str = ch_type.name
            python_type = self.__get_pep249_type(type_name)
            description.append((
                name,
                python_type,
                None,  # display_size
                None,  # internal_size
                None,  # precision
                None,  # scale
                ch_type.nullable,  # null_ok
            ))
        return description

    def _parse_insert_statement(self, sql: str) -> tuple[str, list[str]] | None:
        """Extract table name and column list from INSERT statement. Returns (table, columns) or None."""
        m = re.match(
            r"^\s*INSERT\s+INTO\s+`?(\w+)`?\s+", sql, re.IGNORECASE | re.DOTALL
        )
        if not m:
            return None
        table = m.group(1)

        m2 = re.search(r"\(([^)]+)\)", sql)
        if not m2:
            return None
        raw_cols = m2.group(1)
        columns = []
        for c in raw_cols.split(","):
            c = c.strip()
            c = c.strip("`\"[]")
            columns.append(c.split()[0])
        return (table, columns)

    def __convert_positional_to_pyformat(self, operation: str, params: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
        """Convert %? placeholders to pyformat %(pN)s placeholders and build a params dict."""
        param_dict: dict[str, Any] = {}
        result: list[str] = []
        i = 0
        for part in re.split(r'(%\?)', operation):
            if part == '%?':
                name = f'p{i}'
                param_dict[name] = params[i]
                result.append(f'%({name})s')
                i += 1
            else:
                result.append(part)
        return ''.join(result), param_dict

    async def execute(self, operation: str, params: DbParams | None = None) -> None:
        if params is not None:
            param_tuple: tuple[Any, ...] = tuple(params)
            pyformat_sql, pyformat_params = self.__convert_positional_to_pyformat(operation, param_tuple)
            result = await self.__client.query(pyformat_sql, parameters=pyformat_params or None)
            self.__result = [tuple(row) for row in result.result_rows]
            self.__description = self.__build_description(result.column_names, result.column_types)
            self.__rowcount = result.row_count
            self.__query_index = 0
        else:
            result = await self.__client.query(operation)
            self.__result = [tuple(row) for row in result.result_rows]
            self.__description = self.__build_description(result.column_names, result.column_types)
            self.__rowcount = result.row_count
            self.__query_index = 0

    async def executemany(self, operation: str, seq_params: Sequence[DbParams]) -> None:
        tuple_list: list[DbParams] = []
        for p in seq_params:
            if isinstance(p, (tuple, list)):
                tuple_list.append(tuple(p))
            else:
                tuple_list.append(p)
        if tuple_list:
            first = tuple_list[0]
            parsed_stmt = self._parse_insert_statement(operation)
            if parsed_stmt is not None:
                table, columns = parsed_stmt
                if len(first) == len(columns):
                    try:
                        all_data = [list(p) for p in tuple_list]
                        summary = await self.__client.insert(table=table, data=all_data, column_names=columns)
                        self.__rowcount = summary.written_rows if hasattr(summary, 'written_rows') else 0  # type: ignore[attr-defined]
                        self.__is_insert = True
                        return
                    except Exception:
                        pass
        param_tuples = [tuple(p) if not isinstance(p, tuple) else p for p in seq_params]
        for params_list in param_tuples:
            pyformat_sql, pyformat_params = self.__convert_positional_to_pyformat(operation, params_list)
            query_result = await self.__client.query(pyformat_sql, parameters=pyformat_params or None)
            self.__result = [tuple(row) for row in query_result.result_rows]
            self.__description = self.__build_description(query_result.column_names, query_result.column_types)
            self.__rowcount = query_result.row_count
            self.__query_index = 0

    async def fetchone(self) -> tuple[Any, ...] | None:
        if self.__query_index < len(self.__result):
            row = self.__result[self.__query_index]
            self.__query_index += 1
            return row
        return None

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        end = min(self.__query_index + size, len(self.__result))
        rows = self.__result[self.__query_index:end]
        self.__query_index = end
        return rows

    async def fetchall(self) -> list[tuple[Any, ...]]:
        rows = self.__result[self.__query_index:]
        self.__query_index = len(self.__result)
        return rows

    async def close(self) -> None:
        pass


__all__ = ['AsyncClickHouseProxyCursor']
