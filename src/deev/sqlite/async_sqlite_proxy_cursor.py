# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from sqlite3 import Cursor
from typing import (
    Any,
    Sequence,
)

from ..common.async_db_cursor import AsyncDbCursor
from ..common.db_params import DbParams
from .sqlite_proxy_cursor import SqliteProxyCursor


class AsyncSqliteProxyCursor(AsyncDbCursor):
    """
    Async shim that delegates to ``SqliteProxyCursor``.

    Wraps the synchronous deev cursor proxy and exposes an async API
    using ``asyncio.to_thread`` for underlying sqlite3 operations.
    """
    __sync_cursor: SqliteProxyCursor
    __cursor: Cursor
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: Cursor) -> None:
        self.__cursor = provider_cursor
        self.__sync_cursor = SqliteProxyCursor(provider_cursor)
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'

    @property
    def description(self) -> Sequence[tuple[Any, ...]] | None:
        return self.__cursor.description

    @property
    def lastrowid(self) -> int | None:
        return self.__cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    async def execute(self, operation: str, params: DbParams | None = None) -> None:
        if params is not None:
            operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        loop = asyncio.get_event_loop()
        if params is None:
            await loop.run_in_executor(None, self.__cursor.execute, operation)
        else:
            await loop.run_in_executor(None, self.__cursor.execute, operation, params)

    async def executemany(self, operation: str, seq_params: Sequence[DbParams]) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.__cursor.executemany, operation, seq_params)

    async def fetchone(self) -> tuple[Any, ...] | None:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.__cursor.fetchone)

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.__cursor.fetchmany, size)

    async def fetchall(self) -> list[tuple[Any, ...]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.__cursor.fetchall)

    async def close(self) -> None:
        await asyncio.to_thread(self.__cursor.close)


__all__ = ['AsyncSqliteProxyCursor']
