# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, AsyncGenerator, Literal, Self, cast

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_transaction_context import AsyncDbTransactionContext
from ..common.db_context import AsyncDbContext
from ..common.db_parameters import DbParameters
from .async_sqlite_proxy_connection import AsyncSQLiteProxyConnection
from .async_sqlite_proxy_cursor import AsyncSQLiteProxyCursor
from .sqlite_proxy_cursor import SQLiteProxyCursor
from .sqlite_proxy_connection import SQLiteProxyConnection
from .sqlite_transaction_context import SQLiteTransactionContext


class AsyncSQLiteTransactionContext(AsyncDbTransactionContext):
    """
    Async shim that delegates to ``SQLiteTransactionContext``.

    Wraps the synchronous transaction context and exposes an async API
    using direct method calls — no ``asyncio.to_thread``.
    """

    __context: AsyncDbContext | None
    __inner_ctx: SQLiteTransactionContext | None
    __owns_context: bool

    def __init__(self, context: AsyncDbContext, *, owns_context: bool | None = None) -> None:
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (AsyncSQLiteProxyConnection, AsyncSQLiteTransactionContext))
        self.__context = context if self.__is_deev_context else AsyncSQLiteProxyConnection(context)  # type: ignore[arg-type]
        self.__inner_ctx = None

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

    def __get_inner_ctx(self) -> SQLiteTransactionContext:
        """Return the underlying sync transaction context, acquiring it if necessary."""
        if self.__inner_ctx is None:
            self.__inner_ctx = SQLiteTransactionContext(
                context=cast(AsyncSQLiteProxyConnection, self.__context).sqlite_connection,
                owns_context=self.__owns_context
            )
            self.__inner_ctx.__enter__()
        return self.__inner_ctx

    async def __aenter__(self) -> Self:
        self.__get_inner_ctx()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        if self.__inner_ctx is not None:
            self.__inner_ctx.__exit__(exc_type, exc_value, traceback)
        await self.close()
        return False

    @property
    def connection(self) -> AsyncDbConnection:
        if isinstance(self.__context, AsyncDbTransactionContext):
            return cast(AsyncDbTransactionContext, self.__context).connection
        else:
            return cast(AsyncDbConnection, self.__context)

    @property
    def transaction_name(self) -> str | None:
        return self.__get_inner_ctx().transaction_name

    @property
    def savepoints(self) -> tuple[str, ...]:
        return self.__get_inner_ctx().savepoints

    async def begin_transaction(self, name: str | None = None) -> Self:
        self.__get_inner_ctx().begin_transaction(name)
        return self

    async def create_savepoint(self, name: str | None = None) -> Self:
        self.__get_inner_ctx().create_savepoint(name)
        return self

    async def rollback_savepoint(self, name: str | None = None) -> None:
        self.__get_inner_ctx().rollback_savepoint(name)

    async def close(self) -> None:
        if self.__inner_ctx is not None:
            self.__inner_ctx.close()

    async def commit(self) -> None:
        self.__get_inner_ctx().commit()

    async def cursor(self) -> Any:
        sync_cursor = self.__get_inner_ctx().cursor()
        raw_cursor = sync_cursor._SQLiteProxyCursor__cursor  # type: ignore[attr-defined]
        return AsyncSQLiteProxyCursor(raw_cursor)

    async def execute(self, sql: str, parameters: DbParameters | None = None, raw: bool | None = False) -> Any:
        return self.__get_inner_ctx().execute(sql, parameters, raw)

    async def execute_nonquery(self, sql: str, parameters: DbParameters | None = None) -> None:
        self.__get_inner_ctx().execute_nonquery(sql, parameters)

    async def execute_reader(self, sql: str, parameters: DbParameters | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        sync_gen = self.__get_inner_ctx().execute_reader(sql, parameters)
        for row in sync_gen:
            yield row

    async def execute_scalar(self, sql: str, parameters: DbParameters | None = None) -> Any:
        return self.__get_inner_ctx().execute_scalar(sql, parameters)

    async def execute_script(self, sql: str, raw: str | None = None) -> None:
        self.__get_inner_ctx().execute_script(sql, raw)

    async def rollback(self, name: str | None = None) -> None:
        self.__get_inner_ctx().rollback(name)


__all__ = ['AsyncSQLiteTransactionContext']
