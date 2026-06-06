# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from sqlite3 import Connection
from types import TracebackType
from typing import Any, Literal, Optional, Self

from ..common.DbConnection import DbConnection
from ..common.DbCursor import DbCursor
from .SqliteProxyCursor import SqliteProxyCursor


class SqliteProxyConnection(DbConnection):
    """
    Normalized connection interface for sqlite3.

    Ensures features are preserved wherever a connection or cursor is acquired via ``deev``.
    """

    __connection: Connection

    def __init__(self, provider_connection: Connection) -> None:
        self.__connection = provider_connection

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        return SqliteProxyCursor(self.__connection.cursor(*args, **kwargs))

    def commit(self) -> None:
        self.__connection.commit()

    def rollback(self) -> None:
        self.__connection.rollback()

    def close(self) -> None:
        self.__connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType], /) -> Literal[False]:
        return self.__connection.__exit__(exc_type, exc, tb)


__all__ = ['SqliteProxyConnection']
