# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from sqlite3 import Connection, Cursor
from types import TracebackType
from typing import Any, Literal, Self

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_cursor import AsyncDbCursor
from .async_sqlite_proxy_cursor import AsyncSqliteProxyCursor
from .sqlite_proxy_connection import SqliteProxyConnection


class AsyncSqliteProxyConnection(AsyncDbConnection):
    """
    Async shim that delegates to ``SqliteProxyConnection``.

    Since sqlite3 has no native async API, all calls are forwarded to the
    synchronous proxy using ``asyncio.to_thread``.
    """

    __sync_conn: SqliteProxyConnection

    def __init__(self, conn: Connection) -> None:
        self.__sync_conn = SqliteProxyConnection(conn)

    @property
    def sqlite_connection(self) -> SqliteProxyConnection:
        return self.__sync_conn

    async def cursor(self, *args: Any, **kwargs: Any) -> AsyncDbCursor:
        return AsyncSqliteProxyCursor(self.__sync_conn.cursor(*args, **kwargs))  # type: ignore[arg-type]

    async def commit(self) -> None:
        await asyncio.to_thread(self.__sync_conn.commit)

    async def rollback(self) -> None:
        await asyncio.to_thread(self.__sync_conn.rollback)

    async def close(self) -> None:
        await asyncio.to_thread(self.__sync_conn.close)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> Literal[False]:
        self.__sync_conn.__exit__(exc_type, exc, tb)
        return False


__all__ = ['AsyncSqliteProxyConnection']
