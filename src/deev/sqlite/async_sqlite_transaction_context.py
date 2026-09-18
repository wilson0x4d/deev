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

    __context: AsyncDbContext | None
    __sync_ctx: SqliteTransactionContext | None

    def __init__(self, context: AsyncDbContext, *, owns_context: bool | None = None) -> None:
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (AsyncSqliteProxyConnection, AsyncSqliteTransactionContext))
        self.__context = context if self.__is_deev_context else AsyncSqliteProxyConnection(context)  # type: ignore[arg-type]
        self.__sync_ctx = SqliteTransactionContext(
            context=cast(AsyncSqliteProxyConnection, self.connection).sqlite_connection,
            owns_context=owns_context
        )

    def __del__(self) -> None:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                loop.create_task(self.close())
            else:
                asyncio.run(self.close())
        except Exception:
            pass

    async def __aenter__(self) -> Self:
        assert self.__sync_ctx is not None, 'invalid state'
        await asyncio.to_thread(self.__sync_ctx.begin_transaction)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        try:
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
        finally:
            await self.close()

    @property
    def connection(self) -> AsyncDbConnection:
        assert self.__context is not None, 'no context'
        if isinstance(self.__context, AsyncDbTransactionContext):
            return cast(AsyncDbTransactionContext, self.__context).connection
        else:
            return cast(AsyncDbConnection, self.__context)

    async def begin_transaction(self) -> AsyncDbTransactionContext:
        assert self.__sync_ctx is not None, 'no context'
        await asyncio.to_thread(self.__sync_ctx.begin_transaction)
        return self

    async def close(self) -> None:
        try:
            if self.__sync_ctx is not None:
                self.__sync_ctx.close()
        except Exception:
            pass
        self.__sync_ctx = None

    async def commit(self) -> None:
        assert self.__sync_ctx is not None, 'no context'
        await asyncio.to_thread(self.__sync_ctx.commit)

    async def cursor(self) -> Any:
        assert self.__sync_ctx is not None, 'no context'
        sync_cursor = self.__sync_ctx.cursor()  # type: ignore[arg-type]
        raw_cursor = sync_cursor._SqliteProxyCursor__cursor  # type: ignore[attr-defined]
        return AsyncSqliteProxyCursor(raw_cursor)

    async def execute(self, sql: str, params: DbParams | None = None) -> Any:
        assert self.__sync_ctx is not None, 'no context'
        await asyncio.to_thread(self.__sync_ctx.execute, sql, params)
        return await self.cursor()

    async def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        assert self.__sync_ctx is not None, 'no context'
        await asyncio.to_thread(self.__sync_ctx.execute_nonquery, sql, params)

    async def execute_reader(self, sql: str, params: DbParams | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        assert self.__sync_ctx is not None, 'no context'
        sync_gen = self.__sync_ctx.execute_reader(sql, params)
        loop = asyncio.get_event_loop()
        while True:
            try:
                yield await loop.run_in_executor(None, next, sync_gen)
            except StopIteration:
                break

        assert self.__sync_ctx is not None, 'no context'
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__sync_ctx.execute_scalar(sql, params))

    async def execute_script(self, sql: str) -> None:
        assert self.__sync_ctx is not None, 'no context'
        await asyncio.to_thread(self.__sync_ctx.execute_script, sql)

    async def rollback(self) -> None:
        assert self.__sync_ctx is not None, 'no context'
        await asyncio.to_thread(self.__sync_ctx.rollback)


__all__ = ['AsyncSqliteTransactionContext']
