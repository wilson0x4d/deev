# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from mysql.connector.aio import MySQLConnectionAbstract
from mysql.connector.aio import PooledMySQLConnection
from types import TracebackType
from typing import Any, Literal, Self

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_cursor import AsyncDbCursor
from .async_mysql_proxy_cursor import AsyncMysqlProxyCursor


class AsyncMysqlProxyConnection(AsyncDbConnection):
    """
    Async DB-API 2.0 compliant connection interface for ``mysql.connector.aio``.
    """

    __connection: MySQLConnectionAbstract | PooledMySQLConnection

    def __init__(self, provider_connection: MySQLConnectionAbstract | PooledMySQLConnection) -> None:
        self.__connection = provider_connection

    async def cursor(self, *args: Any, **kwargs: Any) -> AsyncDbCursor:
        return AsyncMysqlProxyCursor(await self.__connection.cursor(*args, **kwargs))  # type: ignore[return-value]

    async def commit(self) -> None:
        await self.__connection.commit()

    async def rollback(self) -> None:
        await self.__connection.rollback()

    async def close(self) -> None:
        await self.__connection.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> Literal[False]:
        await self.__connection.close()
        return False


__all__ = ['AsyncMysqlProxyConnection']
