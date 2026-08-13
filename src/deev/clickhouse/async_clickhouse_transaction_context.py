# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, AsyncGenerator, Literal, Self, cast
from uuid import UUID, uuid4

import hanaro

from ..common.async_db_connection import AsyncDbConnection
from ..common.db_context import AsyncDbContext
from ..common.async_db_cursor import AsyncDbCursor
from ..common.async_db_transaction_context import AsyncDbTransactionContext
from ..common.db_error import DbError
from ..common.db_params import DbParams
from .async_clickhouse_proxy_connection import AsyncClickHouseProxyConnection


class AsyncClickHouseTransactionContext(AsyncDbTransactionContext):
    """
    Async transaction context for ClickHouse.

    ClickHouse does not support traditional ACID transactions. All transaction methods are
    no-ops. This context enables using ClickHouse connections with code that expects
    transactional semantics. For example, when swapping providers.
    """

    __ambient_transaction_id: ContextVar = ContextVar('ambient_transaction_id', default=None)
    __context: AsyncDbContext
    __cursor: Any
    __logger: logging.Logger
    __transaction_id: UUID
    __transaction_state: int

    def __init__(self, context: AsyncDbContext) -> None:
        has_cursor_method = hasattr(context, 'cursor') and callable(getattr(context, 'cursor'))
        has_client_prop = hasattr(context, 'clickhouse_client') and hasattr(context, 'commit')
        is_same = has_cursor_method and has_client_prop
        self.__context = context if is_same else AsyncClickHouseProxyConnection(context)  # type: ignore[arg-type]
        self.__logger = hanaro.get_logger()
        self.__transaction_id = uuid4()
        self.__transaction_state = 0
        self.__cursor = None

    def __del__(self) -> None:
        try:
            if self.__cursor is not None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(self.__cursor.close())
                else:
                    asyncio.run(self.__cursor.close())
        except Exception:
            pass

    async def __aenter__(self) -> Self:
        await self.begin_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        return False

    def __update_transaction_state(self, sql: str) -> None:
        sql = sql.lstrip().upper()
        prefix = sql.strip()[:4]
        if prefix in ['CREA', 'DELE', 'DROP', 'INSE', 'UPDA', 'ALTE', 'ALT']:
            self.__transaction_state = 2
        elif prefix in ['COMM', 'ROLL']:
            self.__transaction_state = 3
            if AsyncClickHouseTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
                AsyncClickHouseTransactionContext.__ambient_transaction_id.set(None)
        elif self.__transaction_state == 0:
            self.__transaction_state = 1

    @property
    def connection(self) -> AsyncDbConnection:
        if isinstance(self.__context, AsyncDbTransactionContext):
            return cast(AsyncDbTransactionContext, self.__context).connection
        else:
            return cast(AsyncDbConnection, self.__context)

    @property
    def clickhouse_client(self) -> Any:
        ctx = self.__context
        if hasattr(ctx, 'clickhouse_client'):
            return ctx.clickhouse_client  # type: ignore[return-value]
        return None

    async def begin_transaction(self) -> AsyncDbTransactionContext:
        if self.__transaction_state != 0:
            raise DbError(f'A transaction was already started in this context, cannot begin a new transaction. ({self.__transaction_state})')
        self.__transaction_state = 1
        self.__cursor = await self.__context.cursor()
        if AsyncClickHouseTransactionContext.__ambient_transaction_id.get(None) is None:
            AsyncClickHouseTransactionContext.__ambient_transaction_id.set(self.__transaction_id)
        return self

    async def close(self) -> None:
        pass

    async def commit(self) -> None:
        try:
            await self.__context.commit()
        except Exception:
            pass
        self.__update_transaction_state('COMMIT')

    async def cursor(self) -> AsyncDbCursor:
        return await self.__context.cursor()

    async def execute(self, sql: str, params: DbParams | None = None) -> AsyncDbCursor:  # type: ignore[override]
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        if self.__cursor is None:
            self.__cursor = await self.__context.cursor()
        assert self.__cursor is not None
        await self.__cursor.execute(sql, params)
        return cast(AsyncDbCursor, self.__cursor)

    async def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        if self.__cursor is None:
            self.__cursor = await self.__context.cursor()
        assert self.__cursor is not None
        await self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)

    async def execute_reader(self, sql: str, params: DbParams | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        if self.__cursor is None:
            self.__cursor = await self.__context.cursor()
        assert self.__cursor is not None
        await self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)
        row = await self.__cursor.fetchone()
        while row is not None:
            yield row
            row = await self.__cursor.fetchone()

    async def execute_scalar(self, sql: str, params: DbParams | None = None) -> Any:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        if self.__cursor is None:
            self.__cursor = await self.__context.cursor()
        assert self.__cursor is not None
        await self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)
        row = await self.__cursor.fetchone()
        return None if row is None else row[0]

    async def execute_script(self, sql: str) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state("INSERT")
        if self.__cursor is None:
            self.__cursor = await self.__context.cursor()
        assert self.__cursor is not None
        await self.__cursor.execute(sql)

    async def rollback(self) -> None:
        try:
            await self.__context.rollback()
        except Exception:
            pass
        self.__update_transaction_state('ROLLBACK')


__all__ = ['AsyncClickHouseTransactionContext']
