# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from clickhouse_connect.driver.client import Client
from clickhouse_connect.dbapi.connection import Connection
from types import TracebackType
from typing import Any, Self

from ..common.db_connection import DbConnection
from ..common.db_cursor import DbCursor
from .clickhouse_proxy_cursor import ClickHouseProxyCursor


class ClickHouseProxyConnection(DbConnection):
    """
    Normalized connection interface for clickhouse-connect.

    Ensures features are preserved wherever a connection or cursor is acquired via ``deev``.
    """

    __connection: Connection

    def __init__(self, provider_connection: Connection, **kwargs: Any) -> None:
        self.__connection = provider_connection
        self.__is_replicated: bool = bool(kwargs.get('replicated', None)) is True or str(kwargs.get('engine', None)).lower().startswith('replicated')

    @property
    def clickhouse_client(self) -> Client:
        """The underlying clickhouse_connect.Client for direct access."""
        return self.__connection.client

    @property
    def is_replicated(self) -> bool:
        return self.__is_replicated

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        return ClickHouseProxyCursor(self.__connection.cursor(*args, **kwargs))  # type: ignore[arg-type]

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.__connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> bool:
        try:
            self.__connection.close()
        except Exception:
            pass
        return exc is not None
