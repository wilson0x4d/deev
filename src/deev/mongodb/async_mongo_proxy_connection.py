# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from types import TracebackType
from typing import Any, Literal, Self

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_cursor import AsyncDbCursor
from .async_mongo_proxy_cursor import AsyncMongoProxyCursor

class AsyncMongoProxyConnection(AsyncDbConnection):
    """
    Async DB-API 2.0 compliant connection interface for MongoDB.
    """
    __client: AsyncMongoClient[Any]
    __database_name: str

    def __init__(self, provider_connection: AsyncMongoClient[Any], database_name: str) -> None:
        self.__client = provider_connection
        self.__database_name = database_name

    @property
    def mongo_client(self) -> AsyncMongoClient[Any]:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.__client

    @property
    def mongo_database(self) -> AsyncDatabase[Any]:
        # NOTE: this is a non-conformant property that we require for migration scripts (QOL), and must be retained.
        return self.mongo_client[self.mongo_database_name]

    @property
    def mongo_database_name(self) -> str:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.__database_name.split('?')[0]

    async def cursor(self, *args: Any, **kwargs: Any) -> AsyncDbCursor:
        return AsyncMongoProxyCursor(self.mongo_client.start_session(), self.mongo_database_name)  # type: ignore[return-value]

    async def commit(self) -> None:
        # MongoDB transactions are session-based; for non-sessioned connections this is a no-op.
        # Use AsyncMongoTransactionContext for transactional operations.
        pass

    async def rollback(self) -> None:
        # MongoDB transactions are session-based; for non-sessioned connections this is a no-op.
        # Use AsyncMongoTransactionContext for transactional operations.
        pass

    async def close(self) -> None:
        await self.mongo_client.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> Literal[False]:
        return False

__all__ = ['AsyncMongoProxyConnection']
