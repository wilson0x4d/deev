# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection
from types import TracebackType
from typing import Any, Literal, Optional

from ..common.DbConnection import DbConnection
from ..common.DbCursor import DbCursor
from .MysqlProxyCursor import MysqlProxyCursor


class MysqlProxyConnection(DbConnection):
    """
    Normalized connection interface for MySQL Connector.

    Ensures normalization features are preserved wherever a connection or cursor is acquired within ``deev``.
    """

    __connection: MySQLConnectionAbstract | PooledMySQLConnection

    def __init__(self, provider_connection: MySQLConnectionAbstract | PooledMySQLConnection) -> None:
        self.__connection = provider_connection

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        return MysqlProxyCursor(self.__connection.cursor(*args, **kwargs))

    def commit(self) -> None:
        self.__connection.commit()

    def rollback(self) -> None:
        self.__connection.rollback()

    def close(self) -> None:
        self.__connection.close()

    def __enter__(self) -> DbConnection:
        return MysqlProxyConnection(self.__connection.__enter__())

    def __exit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType], /) -> Literal[False]:
        self.__connection.__exit__(exc_type, exc, tb)  # type: ignore[arg-type]
        return False


__all__ = ['MysqlProxyConnection']
