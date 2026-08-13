# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, AsyncGenerator, Literal, Self, cast

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_cursor import AsyncDbCursor
from ..common.async_db_transaction_context import AsyncDbTransactionContext
from ..common.db_context import AsyncDbContext
from ..common.db_error import DbError
from ..common.db_params import DbParams
from .async_sqlite_proxy_connection import AsyncSqliteProxyConnection
from .async_sqlite_proxy_cursor import AsyncSqliteProxyCursor
from .sqlite_proxy_cursor import SqliteProxyCursor
from .sqlite_proxy_connection import SqliteProxyConnection
from .sqlite_transaction_context import SqliteTransactionContext


class AsyncSqliteTransactionContext(AsyncDbTransactionContext):
    """
    Async shim that delegates to ``SqliteTransactionContext``.

    Wraps the synchronous transaction context and exposes an async API
    using ``asyncio.to_thread`` for underlying sqlite3 operations.
    """

    __context: AsyncDbContext
    __sync_ctx: SqliteTransactionContext

    def __init__(self, context: AsyncDbContext) -> None:
        self.__context = context
        self.__sync_ctx = SqliteTransactionContext(
            context=cast(AsyncSqliteProxyConnection, self.connection).sqlite_connection
        )

    def __del__(self) -> None:
        try:
            cursor = self.__sync_ctx._SqliteTransactionContext__cursor  # type: ignore[attr-defined]
            if cursor is not None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                sync_cursor = cursor._SqliteProxyCursor__cursor  # type: ignore[attr-defined]
                if loop and loop.is_running():
                    loop.create_task(asyncio.to_thread(sync_cursor.close))
                else:
                    asyncio.run(asyncio.to_thread(sync_cursor.close))
        except Exception:
            pass

    async def __aenter__(self) -> Self:
        await asyncio.to_thread(self.__sync_ctx.begin_transaction)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        if exc_type is not None and self.__sync_ctx._SqliteTransactionContext__transaction_state == 2:  # type: ignore[attr-defined]
            await self.rollback()
        elif self.__sync_ctx._SqliteTransactionContext__transaction_state == 2:  # type: ignore[attr-defined]
            await self.rollback()
            raise DbError('Detected uncommitted transaction, rolling back. You must explicitly call commit or rollback.')
        elif self.__sync_ctx._SqliteTransactionContext__transaction_state <= 1:  # type: ignore[attr-defined]
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
        return False

    @property
    def connection(self) -> AsyncDbConnection:
        if isinstance(self.__context, AsyncDbTransactionContext):
            return cast(AsyncDbTransactionContext, self.__context).connection
        else:
            return cast(AsyncDbConnection, self.__context)

    async def begin_transaction(self) -> AsyncDbTransactionContext:
        await asyncio.to_thread(self.__sync_ctx.begin_transaction)
        return self

    async def close(self) -> None:
        pass

    async def commit(self) -> None:
        await asyncio.to_thread(self.__sync_ctx.commit)

    async def cursor(self) -> Any:
        sync_cursor = self.__sync_ctx.cursor()  # type: ignore[arg-type]
        raw_cursor = sync_cursor._SqliteProxyCursor__cursor  # type: ignore[attr-defined]
        return AsyncSqliteProxyCursor(raw_cursor)

    async def execute(self, sql: str, params: DbParams | None = None) -> Any:
        await asyncio.to_thread(self.__sync_ctx.execute, sql, params)
        return await self.cursor()

    async def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        await asyncio.to_thread(self.__sync_ctx.execute_nonquery, sql, params)

    async def execute_reader(self, sql: str, params: DbParams | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        sync_gen = self.__sync_ctx.execute_reader(sql, params)
        loop = asyncio.get_event_loop()
        while True:
            try:
                yield await loop.run_in_executor(None, next, sync_gen)
            except StopIteration:
                break

    async def execute_scalar(self, sql: str, params: DbParams | None = None) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__sync_ctx.execute_scalar(sql, params))

    async def execute_script(self, sql: str) -> None:
        await asyncio.to_thread(self.__sync_ctx.execute_script, sql)

    async def rollback(self) -> None:
        await asyncio.to_thread(self.__sync_ctx.rollback)


__all__ = ['AsyncSqliteTransactionContext']
