# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.dbapi.connection import Connection
from types import TracebackType
from typing import Any, Self

from ..common.async_db_connection import AsyncDbConnection
from ..common.async_db_cursor import AsyncDbCursor
from .async_clickhouse_proxy_cursor import AsyncClickHouseProxyCursor


class AsyncClickHouseProxyConnection(AsyncDbConnection):
    """
    Normalized async connection interface for clickhouse-connect.

    Ensures features are preserved wherever a connection or cursor is acquired via ``deev``.
    """

    __connection: AsyncClient

    def __init__(self, provider_connection: AsyncClient, **kwargs: Any) -> None:
        self.__connection = provider_connection
        self.__is_replicated: bool = bool(kwargs.get('replicated', None)) is True or str(kwargs.get('engine', None)).lower().startswith('replicated')

    @property
    def clickhouse_client(self) -> AsyncClient:
        """The underlying clickhouse_connect.driver.client.AsyncClient for direct access."""
        return self.__connection

    @property
    def is_replicated(self) -> bool:
        return self.__is_replicated

    async def cursor(self, *args: Any, **kwargs: Any) -> AsyncDbCursor:
        return AsyncClickHouseProxyCursor(self.__connection, *args, **kwargs)  # type: ignore[arg-type]

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        await self.__connection.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> bool:
        try:
            await self.__connection.close()
        except Exception:
            pass
        return exc is not None


__all__ = ['AsyncClickHouseProxyConnection']
