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
from ..common.db_parameters import DbParameters
from .async_sqlite_proxy_connection import AsyncSQLiteProxyConnection
from .async_sqlite_proxy_cursor import AsyncSQLiteProxyCursor
from .sqlite_proxy_cursor import SQLiteProxyCursor
from .sqlite_proxy_connection import SQLiteProxyConnection
from .sqlite_transaction_context import SQLiteTransactionContext


class AsyncSQLiteTransactionContext(AsyncDbTransactionContext):
    """
    Async shim that delegates to ``SQLiteTransactionContext``.
    """

    __context: AsyncDbContext | None
    __sync_ctx: SQLiteTransactionContext | None

    def __init__(self, context: AsyncDbContext, *, owns_context: bool | None = None) -> None:
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (AsyncSQLiteProxyConnection, AsyncSQLiteTransactionContext))
        self.__context = context if self.__is_deev_context else AsyncSQLiteProxyConnection(context)  # type: ignore[arg-type]
        self.__sync_ctx = SQLiteTransactionContext(
            context=cast(AsyncSQLiteProxyConnection, self.connection).sqlite_connection,
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
        self.__sync_ctx.begin_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        try:
            if self.__sync_ctx is not None:
                self.__sync_ctx.__exit__(exc_type, exc_value, traceback)
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
        self.__sync_ctx.begin_transaction()
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
        self.__sync_ctx.commit()

    async def cursor(self) -> Any:
        assert self.__sync_ctx is not None, 'no context'
        sync_cursor = self.__sync_ctx.cursor()  # type: ignore[arg-type]
        raw_cursor = sync_cursor._SQLiteProxyCursor__cursor  # type: ignore[attr-defined]
        return AsyncSQLiteProxyCursor(raw_cursor)

    async def execute(self, sql: str, parameters: DbParameters | None = None) -> Any:
        assert self.__sync_ctx is not None, 'no context'
        self.__sync_ctx.execute(sql, parameters)
        return await self.cursor()

    async def execute_nonquery(self, sql: str, parameters: DbParameters | None = None) -> None:
        assert self.__sync_ctx is not None, 'no context'
        self.__sync_ctx.execute_nonquery(sql, parameters)

    async def execute_reader(self, sql: str, parameters: DbParameters | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        assert self.__sync_ctx is not None, 'no context'
        sync_gen = self.__sync_ctx.execute_reader(sql, parameters)
        while True:
            try:
                yield next(sync_gen)
            except StopIteration:
                break

    async def execute_scalar(self, sql: str, parameters: DbParameters | None = None) -> Any:
        assert self.__sync_ctx is not None, 'no context'
        return self.__sync_ctx.execute_scalar(sql, parameters)

    async def execute_script(self, sql: str) -> None:
        assert self.__sync_ctx is not None, 'no context'
        self.__sync_ctx.execute_script(sql)

    async def rollback(self) -> None:
        assert self.__sync_ctx is not None, 'no context'
        self.__sync_ctx.rollback()


__all__ = ['AsyncSQLiteTransactionContext']
