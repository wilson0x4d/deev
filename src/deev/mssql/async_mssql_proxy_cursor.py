# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from mssql_python import Cursor
from typing import (
    Any,
    Sequence,
    cast,
)

from ..common.async_db_cursor import AsyncDbCursor, AsyncDbCursorDescription
from ..common.db_parameters import DbParameters
from .mssql_proxy_cursor import MSSQLProxyCursor


class AsyncMSSQLProxyCursor(AsyncDbCursor):
    """
    Async shim that delegates to ``MSSQLProxyCursor``.

    Wraps the synchronous deev cursor proxy and exposes an async API
    using ``asyncio.to_thread`` for underlying mssql_python operations.
    """
    __sync_cursor: MSSQLProxyCursor
    __cursor: Cursor
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: Cursor) -> None:
        self.__cursor = provider_cursor
        self.__sync_cursor = MSSQLProxyCursor(provider_cursor)
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'

    @property
    def description(self) -> AsyncDbCursorDescription:
        return cast(AsyncDbCursorDescription, self.__cursor.description)

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
        self.__cursor.executemany(operation, [tuple(p) if isinstance(p, (tuple, list)) else dict(p) for p in seq_of_parameters])  # type: ignore[arg-type]

    async def fetchone(self) -> tuple[Any, ...] | None:
        return cast(tuple[Any, ...] | None, self.__cursor.fetchone())

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return cast(list[tuple[Any, ...]], self.__cursor.fetchmany(size))

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return cast(list[tuple[Any, ...]], self.__cursor.fetchall())

    async def close(self) -> None:
        await asyncio.to_thread(self.__cursor.close)


__all__ = ['AsyncMSSQLProxyCursor']
