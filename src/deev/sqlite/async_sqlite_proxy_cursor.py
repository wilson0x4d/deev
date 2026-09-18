# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from sqlite3 import Cursor
from typing import (
    Any,
    Sequence,
)

from ..common.async_db_cursor import AsyncDbCursor, AsyncDbCursorDescription
from ..common.db_parameters import DbParameters
from .sqlite_proxy_cursor import SQLiteProxyCursor


class AsyncSQLiteProxyCursor(AsyncDbCursor):
    """
    Async shim that delegates to ``SQLiteProxyCursor``.
    """
    __sync_cursor: SQLiteProxyCursor
    __cursor: Cursor
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: Cursor) -> None:
        self.__cursor = provider_cursor
        self.__sync_cursor = SQLiteProxyCursor(provider_cursor)
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'

    @property
    def description(self) -> AsyncDbCursorDescription:
        return self.__cursor.description  # type: ignore[return-value]

    @property
    def lastrowid(self) -> int | None:
        return self.__cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    async def execute(self, operation: str, parameters: DbParameters | None = None) -> None:
        if parameters is not None:
            operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        if parameters is None:
            self.__cursor.execute(operation)
        else:
            self.__cursor.execute(operation, parameters)

    async def executemany(self, operation: str, seq_of_parameters: Sequence[DbParameters]) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.executemany(operation, seq_of_parameters)

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.__cursor.fetchone()

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchmany(size)

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchall()

    async def close(self) -> None:
        self.__cursor.close()


__all__ = ['AsyncSQLiteProxyCursor']
