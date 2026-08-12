# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Optional, Sequence

import hanaro

from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_params import DbParams

if TYPE_CHECKING:
    from clickhouse_connect.dbapi.cursor import Cursor
    from clickhouse_connect.driver.client import Client


class ClickHouseProxyCursor(DbCursor):
    """
    Normalized cursor interface for clickhouse-connect.

    ClickHouse's DBAPI cursor uses pyformat paramstyle (%(name)s), but deev standardizes on
    positional parameters (%?). This cursor converts positional params to pyformat format
    by generating parameter names like %(p0)s, %(p1)s, etc.

    INSERT statements in execute/executemany are routed through the native ``client.insert()``
    method for optimal performance.
    """

    __cursor: Cursor
    __logger: logging.Logger

    def __init__(self, provider_cursor: Cursor) -> None:
        self.__cursor = provider_cursor
        self.__logger = hanaro.get_logger()

    @property
    def clickhouse_client(self) -> Client:
        """The underlying clickhouse_connect.Client used by the cursor."""
        return self.__cursor.client

    @property
    def description(self) -> Optional[Sequence[tuple[Any, ...]]]:
        return self.__cursor.description

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    @property
    def summary(self) -> list[dict[str, Any]]:
        return self.__cursor.summary

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

    def _try_client_bulk_insert(self, sql: str, params: tuple[Any, ...] | Sequence[tuple[Any, ...]]) -> bool:
        """Try to execute an INSERT via the native client."""
        result = self._parse_insert_statement(sql)
        if result is None:
            return False
        table, columns = result

        first: tuple[Any, ...] | Sequence[tuple[Any, ...]]
        if not isinstance(params, tuple):
            if not params:
                return False
            if isinstance(params[0], tuple):
                first = params[0]
            else:
                first = params
        else:
            first = params

        if len(first) != len(columns):
            return False

        client = self.__cursor.client
        all_data = [list(first)] if isinstance(params, tuple) else [list(p) for p in params]
        try:
            summary = client.insert(
                table=table,
                data=all_data,
                column_names=columns
            )
            self.__cursor._rowcount = summary.written_rows  # type: ignore[attr-defined]
            self.__cursor.data = []  # type: ignore[attr-defined]
            return True
        except Exception:
            return False

    def __convert_positional_to_pyformat(self, operation: str, params: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
        """Convert %? placeholders to pyformat %(pN)s placeholders and build a params dict."""
        param_dict: dict[str, Any] = {}
        result: list[str] = []
        i = 0
        for part in re.split(r'(%\?)', operation):
            if part == '%?':
                name = f'p{i}'
                param_dict[name] = params[i]
                result.append(f'(%({name})s)')
                i += 1
            else:
                result.append(part)
        return ''.join(result), param_dict

    def execute(self, operation: str, params: Optional[DbParams] = None) -> None:
        if params is not None:
            param_tuple: tuple[Any, ...] = tuple(params)
            pyformat_sql, pyformat_params = self.__convert_positional_to_pyformat(operation, param_tuple)
            # Try native client INSERT first
            if self._try_client_bulk_insert(operation, param_tuple):
                return
            self.__cursor.execute(pyformat_sql, parameters=pyformat_params)
        else:
            self.__cursor.execute(operation)

    def executemany(self, operation: str, seq_params: Sequence[DbParams]) -> None:
        tuple_list: list[DbParams] = []
        for p in seq_params:
            if isinstance(p, (tuple, list)):
                tuple_list.append(tuple(p))
            else:
                tuple_list.append(p)
        if tuple_list:
            first = tuple_list[0]
            result = self._parse_insert_statement(operation)
            if result is not None:
                table, columns = result
                if len(first) == len(columns):
                    client = self.__cursor.client
                    try:
                        all_data = [list(p) for p in tuple_list]
                        summary = client.insert(table=table, data=all_data, column_names=columns)
                        self.__cursor._rowcount = summary.written_rows  # type: ignore[attr-defined]
                        self.__cursor.data = []  # type: ignore[attr-defined]
                        return
                    except Exception:
                        pass
        self.__cursor.executemany(operation, [list(p) if not isinstance(p, tuple) else p for p in seq_params])

    def fetchone(self) -> tuple[Any, ...] | None:
        result = self.__cursor.fetchone()
        if result is not None:
            return tuple(result)
        return None

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.__cursor.fetchmany(size)]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.__cursor.fetchall()]

    def close(self) -> None:
        self.__cursor.close()


__all__ = ['ClickHouseProxyCursor']
