# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from types import TracebackType
from typing import Any, AsyncGenerator, Literal, Self, cast
from uuid import uuid4

import pymongo
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_transaction_context import AsyncDbTransactionContext
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.tlc_parser import extract_begin_name, extract_rollback_name, extract_savepoint_name
from .async_mongo_proxy_connection import AsyncMongoProxyConnection
from .async_mongo_proxy_cursor import AsyncMongoProxyCursor


class AsyncMongoTransactionContext(AsyncDbTransactionContext):

    _DELEGATE_TXN_CACHE: dict[tuple[str | None, int], bool] = {}

    __ambient_transaction_id: ContextVar[str | None] = ContextVar[str | None]('ambient_transaction_id', default=None)
    __context: AsyncDbConnection | AsyncDbTransactionContext | None
    __cursor: AsyncMongoProxyCursor | None
    __database_name: str
    __savepoints: list[str]
    __transaction_depth: int
    __transaction_id: str
    __transaction_name: str | None
    __delegate_mode: bool | None

    def __init__(self, context: AsyncDbConnection | AsyncDbTransactionContext, *, owns_context: bool | None = None):
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (AsyncMongoProxyConnection, AsyncMongoTransactionContext))
        mongo_database_name = getattr(context, 'mongo_database_name', None)
        assert mongo_database_name is not None, 'bad init'
        self.__context = context if self.__is_deev_context else AsyncMongoProxyConnection(context, mongo_database_name)  # type: ignore[arg-type]
        self.__transaction_id = uuid4().hex
        self.__transaction_depth = 0
        self.__savepoints: list[str] = []
        self.__transaction_name: str | None = None
        self.__database_name = getattr(context, 'mongo_database_name', '')  # type: ignore[arg-type]
        self.__delegate_mode = AsyncMongoTransactionContext._DELEGATE_TXN_CACHE.get(
            AsyncMongoTransactionContext.__server_key(self.mongo_client), None
        )
        self.__cursor = None

    @staticmethod
    def __server_key(mongo_client: pymongo.AsyncMongoClient[Any]) -> tuple[str | None, int]:
        """Extract (hostname, port) from a pymongo.MongoClient as cache key."""
        return (mongo_client.HOST, mongo_client.PORT)

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
            if self.__transaction_depth > 0:
                if exc_type is not None:
                    await self.rollback()
                else:
                    await self.rollback()
                    raise DbError('Detected uncommitted transaction, rolling back. You must explicitly call commit or rollback.')
        finally:
            await self.close()
            self.__transaction_depth = -1
        return False

    async def __preprocess_sql(self, sql: str) -> str | None:
        """
        Parse SQL to determine whether it is a transaction-control (TLC) keyword
        or a regular SQL statement.

        For MongoDB: all TLC keywords return None (scrubbed) since MongoDB has
        no SQL transaction syntax. Side effects happen via mongo_session.
        """
        if self.__transaction_depth == -1:
            raise DbError('Cannot use a transaction context that has exited.')
        elif self.__transaction_depth == -2:
            raise DbError('Cannot use a transaction context that has been committed.')
        elif self.__transaction_depth == -3:
            raise DbError('Cannot use a transaction context that has been rolled back.')

        sql_upper = sql.lstrip().upper()
        prefix = sql_upper[:4]

        if prefix == 'BEGI':
            self.__transaction_depth += 1
            self.__transaction_name = extract_begin_name(sql)
            if self.__transaction_depth == 1 and not self.__delegate_mode:
                await self.mongo_session.start_transaction()
            return None

        elif prefix == 'SAVE':
            name_token = extract_savepoint_name(sql)
            if name_token:
                self.__savepoints.append(name_token)
            return None

        elif prefix == 'COMM':
            if self.__transaction_depth == 0:
                raise DbError('No active transaction to commit.')
            self.__transaction_depth -= 1
            if self.__transaction_depth == 0:
                self.__savepoints.clear()
                self.__transaction_name = None
                self.__ambient_transaction_id.set(None)
                self.__transaction_depth = -2
            if not self.__delegate_mode and self.__transaction_depth == -2:
                await self.mongo_session.commit_transaction()
            return None

        elif prefix == 'ROLL':
            if self.__transaction_depth == 0:
                raise DbError('Cannot rollback, no transaction.')
            name = extract_rollback_name(sql)

            if name:
                if name in self.__savepoints:
                    while self.__savepoints:
                        sp = self.__savepoints.pop()
                        if sp == name:
                            break
                    return None
                elif name == self.__transaction_name:
                    pass  # full rollback, depth reset below
                else:
                    raise DbError('Invalid Transaction Name')
            else:
                pass  # full rollback, depth reset below

            self.__transaction_depth = -3
            self.__savepoints.clear()
            self.__transaction_name = None
            self.__ambient_transaction_id.set(None)
            if not self.__delegate_mode:
                await self.mongo_session.abort_transaction()
            return None

        return sql

    @property
    def connection(self) -> AsyncDbConnection:
        if isinstance(self.__context, AsyncDbTransactionContext):
            return self.__context.connection
        else:
            return self.__context  # type: ignore[return-value]

    @property
    def mongo_client(self) -> pymongo.AsyncMongoClient[Any]:
        return self.connection.mongo_client  # type: ignore

    @property
    def mongo_database(self) -> Any:
        return self.connection.mongo_client[self.__database_name]  # type: ignore

    @property
    def mongo_database_name(self) -> str:
        return self.__database_name

    @property
    def mongo_session(self) -> AsyncClientSession:
        if self.__cursor is None:
            raise DbError('Cursor not initialized.')
        return self.__cursor.mongo_session

    @property
    def transaction_name(self) -> str | None:
        return self.__transaction_name

    @property
    def savepoints(self) -> tuple[str, ...]:
        return tuple(self.__savepoints)

    async def begin_transaction(self, name: str | None = None) -> Self:
        async with self.connection.mongo_client.start_session() as session:  # type: ignore[attr-defined, union-attr]
            self.__cursor = AsyncMongoProxyCursor(session, self.__database_name)
        if AsyncMongoTransactionContext.__ambient_transaction_id.get(None) is None:
            AsyncMongoTransactionContext.__ambient_transaction_id.set(name or self.__transaction_id)
        sql = 'BEGIN TRANSACTION'
        if name:
            sql += f' {name}'
        await self.execute(sql)
        return self  # type: ignore[return-type]

    async def create_savepoint(self, name: str | None = None) -> Self:
        if name is None:
            name = f'TID_{uuid4().hex[:24]}'
        sql = f'SAVE TRANSACTION {name}'
        await self.execute(sql)
        return self

    async def rollback_savepoint(self, name: str | None = None) -> None:
        if name is None:
            if not self.__savepoints:
                return
            name = self.__savepoints[-1]
        sql = f'ROLLBACK TRANSACTION {name}'
        await self.execute(sql)

    async def close(self) -> None:
        try:
            if self.__cursor is not None:
                await self.__cursor.close()
        except Exception:
            pass
        self.__cursor = None
        try:
            if self.__context is not None and self.__owns_context and hasattr(self.__context, 'close'):
                await self.__context.close()
        except Exception:
            pass
        self.__context = None

    async def commit(self) -> None:
        await self.execute('COMMIT')

    async def cursor(self) -> AsyncMongoProxyCursor:
        if self.__cursor is None:
            raise DbError('Cursor not initialized.')
        return self.__cursor

    async def execute(self, sql: str, parameters: DbParameters | None = None, raw: bool = False) -> AsyncMongoProxyCursor:
        if not raw:
            modified = await self.__preprocess_sql(sql)
            if modified is None:
                from ..common.noop_cursor import NoopCursor
                return cast(AsyncMongoProxyCursor, NoopCursor())  # type: ignore[return-value]
            sql = modified
        assert self.__cursor is not None
        await self.__cursor.execute(
            sql,
            tuple(parameters) if parameters is not None else tuple())
        return self.__cursor  # type: ignore[return-value]

    async def execute_nonquery(self, sql: str, parameters: DbParameters | None = None) -> None:
        await self.execute(sql, parameters)

    async def execute_reader(self, sql: str, parameters: DbParameters | None = None) -> AsyncGenerator[tuple[Any, ...], None]:  # type: ignore[override]
        cursor = await self.execute(sql, parameters)
        row = await cursor.fetchone()
        while row is not None:
            yield row
            row = await cursor.fetchone()

    async def execute_scalar(self, sql: str, parameters: DbParameters | None = None) -> Any:
        cursor = await self.execute(sql, parameters)
        try:
            row = await cursor.fetchone()
            return None if row is None else row[0]
        except Exception:
            return cursor.rowcount

    async def execute_script(self, sql: str, raw: bool = False) -> None:
        if raw is True:
            await self.execute(sql, raw=True)
            return
        lines = sql.split('\n')
        scrubbed = [line for line in lines if await self.__preprocess_sql(line) is not None]
        joined = '\n'.join(scrubbed)
        if joined:
            await self.execute(joined, raw=True)

    async def rollback(self, name: str | None = None) -> None:
        sql = 'ROLLBACK' if name is None else f'ROLLBACK TRANSACTION {name}'
        await self.execute(sql)


__all__ = ['AsyncMongoTransactionContext']
