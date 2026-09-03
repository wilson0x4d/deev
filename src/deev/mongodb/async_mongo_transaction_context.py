# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from types import TracebackType
from typing import Any, AsyncGenerator, Literal, Self, cast

import pymongo
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection
from uuid import UUID, uuid4

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_transaction_context import AsyncDbTransactionContext
from ..common.db_error import DbError
from ..common.db_params import DbParams
from .async_mongo_proxy_connection import AsyncMongoProxyConnection
from .async_mongo_proxy_cursor import AsyncMongoProxyCursor


class AsyncMongoTransactionContext(AsyncDbTransactionContext):

    _DELEGATE_TXN_CACHE: dict[tuple[str | None, int], bool] = {}

    __ambient_transaction_id: ContextVar[UUID | None] = ContextVar[UUID | None]('ambient_transaction_id', default=None)
    __context: AsyncDbConnection | AsyncDbTransactionContext | None
    __cursor: AsyncMongoProxyCursor | None
    __database_name: str
    __transaction_id: UUID
    __transaction_state: int
    __delegate_mode: bool | None

    def __init__(self, context: AsyncDbConnection | AsyncDbTransactionContext):
        self.__owns_context = not isinstance(context, (AsyncMongoProxyConnection, AsyncMongoTransactionContext))
        mongo_database_name = getattr(context, 'mongo_database_name', None)
        assert mongo_database_name is not None, 'bad init'
        self.__context = context if not self.__owns_context else AsyncMongoProxyConnection(context, mongo_database_name)  # type: ignore[arg-type]
        self.__transaction_id = uuid4()
        self.__transaction_state = 0
        self.__database_name = getattr(context, 'mongo_database_name', '')  # type: ignore[arg-type]
        self.__delegate_mode = AsyncMongoTransactionContext._DELEGATE_TXN_CACHE.get(
            AsyncMongoTransactionContext._server_key(self.mongo_client), None
        )
        self.__cursor = None

    @staticmethod
    def _server_key(mongo_client: Any) -> tuple[str | None, int]:
        """Extract (hostname, port) from a pymongo.MongoClient as cache key."""
        return (mongo_client.HOST, mongo_client.PORT)  # type: ignore[attr-defined]

    async def __is_delegate_mode(self) -> bool:
        """Return True when the server is known NOT to support transactions."""
        if self.__delegate_mode is None:
            try:
                self.__delegate_mode = 'replSetName' not in (await cast(AsyncMongoProxyConnection, self.connection).mongo_client.admin.command('ismaster'))  # type: ignore[return-value]
            except Exception:
                self.__delegate_mode = False
        return self.__delegate_mode is True

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
        await self.begin_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        try:
            if await self.__is_delegate_mode():
                self.__transaction_state = 3
                return False
            if exc_type is not None and self.__transaction_state == 2:
                await self.rollback()
            elif self.__transaction_state == 2:
                await self.rollback()
                raise DbError('Detected uncommitted transaction, rolling back. You must explicitly call commit or rollback.')
            elif self.__transaction_state <= 1:
                if exc_type is not None:
                    await self.rollback()
                else:
                    await self.commit()
            return False
        finally:
            await self.close()

    def __update_transaction_state(self, sql: str) -> None:
        sql = sql.lstrip().upper()
        if sql.startswith(('CREATE ', 'DELETE ', 'DROP ', 'INSERT ', 'UPDATE ')):
            self.__transaction_state = 2
        elif sql.startswith(('COMMIT', 'ROLLBACK', 'SAVEPOINT')):
            self.__transaction_state = 3
            if AsyncMongoTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
                AsyncMongoTransactionContext.__ambient_transaction_id.set(None)
        elif self.__transaction_state == 0:
            self.__transaction_state = 1

    @property
    def connection(self) -> AsyncDbConnection:
        if isinstance(self.__context, AsyncDbTransactionContext):
            return self.__context.connection
        else:
            return self.__context  # type: ignore[return-value]

    @property
    def mongo_client(self) -> pymongo.AsyncMongoClient[Any]:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.connection.mongo_client  # type: ignore

    @property
    def mongo_database(self) -> Any:
        # NOTE: this is a non-conformant property that we require for migration scripts (QOL), and must be retained.
        return self.connection.mongo_client[self.__database_name]  # type: ignore

    @property
    def mongo_database_name(self) -> str:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.__database_name

    @property
    def mongo_session(self) -> AsyncClientSession:
        # NOTE: keep this as-is unless you see a problem, then we should discuss first.
        if self.__cursor is None:
            raise DbError('Cursor not initialized.')
        return self.__cursor.mongo_session

    async def begin_transaction(self) -> AsyncDbTransactionContext:
        if self.__transaction_state != 0:
            raise DbError(f'A transaction was already started in this context, cannot begin a new transaction. ({self.__transaction_state})')
        self.__transaction_state = 1
        async with self.connection.mongo_client.start_session() as session:  # type: ignore[attr-defined, union-attr]
            self.__cursor = AsyncMongoProxyCursor(session, self.__database_name)
        if AsyncMongoTransactionContext.__ambient_transaction_id.get(None) is None:
            AsyncMongoTransactionContext.__ambient_transaction_id.set(self.__transaction_id)
            if not await self.__is_delegate_mode():
                raise DbError('AsyncMongoTransactionContext: begin_transaction requires async session setup.')
        return self  # type: ignore[return-type]

    async def close(self) -> None:
        try:
            if self.__cursor is not None:
                await self.__cursor.close()
                self.__cursor = None
        except Exception:
            pass
        try:
            if self.__context is not None and self.__owns_context and hasattr(self.__context, 'close'):
                await self.__context.close()
                self.__context = None
        except Exception:
            pass

    async def commit(self) -> None:
        if self.__cursor is None:
            raise DbError('Cursor not initialized.')
        if not self.__delegate_mode and AsyncMongoTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            await self.mongo_session.commit_transaction()
        self.__update_transaction_state('COMMIT')

    async def cursor(self) -> AsyncMongoProxyCursor:  # type: ignore[override]
        if self.__cursor is None:
            raise DbError('Cursor not initialized.')
        return self.__cursor

    async def execute(self, sql: str, params: DbParams | None = None) -> AsyncMongoProxyCursor:  # type: ignore[override]
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        assert self.__cursor is not None
        await self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        return self.__cursor  # type: ignore[return-value]

    async def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        await self.__cursor.execute(  # type: ignore[union-attr]
            sql,
            tuple(params) if params is not None else tuple())
        self.__update_transaction_state(sql)

    async def execute_reader(self, sql: str, params: DbParams | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        params = tuple(params) if params is not None else tuple()
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
        assert self.__cursor is not None and self.__cursor.rowcount >= 0
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
        await self.mongo_session.database.command(sql)  # type: ignore[arg-type, attr-defined]

    async def rollback(self) -> None:
        self.__update_transaction_state('ROLLBACK')
        if self.__cursor is None:
            return
        if AsyncMongoTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            try:
                await self.mongo_session.abort_transaction()
            except Exception:
                pass
        else:
            pass


__all__ = ['AsyncMongoTransactionContext']
