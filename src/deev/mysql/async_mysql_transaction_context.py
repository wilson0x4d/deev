# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import hanaro
import logging
import mysql.connector
from types import TracebackType
from typing import Any, AsyncGenerator, Literal, Self, cast
from uuid import UUID, uuid4

from ..common.async_db_connection import AsyncDbConnection
from ..common.db_context import AsyncDbContext
from ..common.async_db_cursor import AsyncDbCursor
from ..common.async_db_transaction_context import AsyncDbTransactionContext
from ..common.db_error import DbError
from ..common.db_params import DbParams
from .async_mysql_proxy_connection import AsyncMysqlProxyConnection
from .async_mysql_proxy_cursor import AsyncMysqlProxyCursor


class AsyncMysqlTransactionContext(AsyncDbTransactionContext):

    __ambient_transaction_id: ContextVar = ContextVar('ambient_transacton_id', default=None)
    __context: AsyncDbConnection
    __cursor: AsyncDbCursor
    __logger: logging.Logger
    __transaction_id: UUID
    __transaction_state: int

    def __init__(self, context: AsyncDbContext):
        self.__context = context if isinstance(context, (AsyncMysqlProxyConnection, AsyncMysqlTransactionContext)) else AsyncMysqlProxyConnection(context)  # type: ignore[arg-type]
        self.__logger = hanaro.get_logger()
        self.__transaction_id = uuid4()
        self.__transaction_state = 0

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
        if exc_type is not None and self.__transaction_state == 2:
            await self.rollback()
        elif self.__transaction_state == 2:
            await self.rollback()
            raise DbError('Detected uncommitted transaction, rolling back. You must explicitly call commit or rollback.')
        return False

    def __update_transaction_state(self, sql: str) -> None:
        sql = sql.lstrip().upper()
        prefix = sql.strip()[:4]
        if prefix in ['CREA', 'DELE', 'DROP', 'INSE', 'UPDA']:
            self.__transaction_state = 2
        elif prefix in ['COMM', 'ROLL']:
            self.__transaction_state = 3
            if AsyncMysqlTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
                AsyncMysqlTransactionContext.__ambient_transaction_id.set(None)
        elif self.__transaction_state == 0:
            self.__transaction_state = 1

    @property
    def connection(self) -> AsyncDbConnection:
        if isinstance(self.__context, AsyncDbTransactionContext):
            return cast(AsyncDbTransactionContext, self.__context).connection
        else:
            return cast(AsyncDbConnection, self.__context)

    async def begin_transaction(self) -> AsyncDbTransactionContext:
        if self.__transaction_state != 0:
            raise DbError(f'A transaction was already started in this context, cannot begin a new transaction. ({self.__transaction_state})')
        self.__transaction_state = 1
        self.__cursor = await self.__context.cursor()
        if AsyncMysqlTransactionContext.__ambient_transaction_id.get(None) is None:
            AsyncMysqlTransactionContext.__ambient_transaction_id.set(self.__transaction_id)
            await self.__cursor.execute('START TRANSACTION')
        else:
            await self.__cursor.execute(f'SAVEPOINT TID_{self.__transaction_id.hex}')
        return self

    async def close(self) -> None:
        # only defined for cross-compat with `AsyncDbConnection`
        pass

    async def commit(self) -> None:
        if AsyncMysqlTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            await self.__context.commit()
        else:
            await self.__cursor.execute(f'RELEASE SAVEPOINT TID_{self.__transaction_id.hex}')
        self.__update_transaction_state('COMMIT')

    async def cursor(self) -> AsyncDbCursor:
        return await self.__context.cursor()

    async def execute(self, sql: str, params: DbParams | None = None) -> AsyncMysqlProxyCursor:  # type: ignore[override]
        """
        An async `execute` method that more closely conforms to PEP 249 (to facilitate drop-in use cases.)

        :param sql: A string containing the SQL statement to execute.
        :param params: A tuple containing the params to substitute into the SQL statement.
        :return: The cursor object the caller can use to retrieve results.
        """
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        await self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        return cast(AsyncMysqlProxyCursor, self.__cursor)

    async def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        await self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        self.__update_transaction_state(sql)

    async def execute_reader(self, sql: str, params: DbParams | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        params = tuple(params) if params is not None else tuple()
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
        await self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple()
        )
        self.__update_transaction_state(sql)
        row = await self.__cursor.fetchone()
        return None if row is None else row[0]

    async def execute_script(self, sql: str) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state("INSERT")
        await self.__cursor.execute(sql)

    async def rollback(self) -> None:
        if AsyncMysqlTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            try:
                await self.__cursor.execute('ROLLBACK')
            except mysql.connector.Error:
                self.__logger
        else:
            try:
                await self.__cursor.execute(f'ROLLBACK TO SAVEPOINT TID_{self.__transaction_id.hex}')
            except mysql.connector.Error as e:
                if 'does not exist' in str(e):
                    # DDL implicitly released all savepoints (MySQL behavior)
                    try:
                        await self.__cursor.execute('ROLLBACK')
                    except mysql.connector.Error:
                        pass
                else:
                    raise
        self.__update_transaction_state('ROLLBACK')


__all__ = ['AsyncMysqlTransactionContext']
