# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from mssql_python import Connection
from types import TracebackType
from typing import Any, Literal, Self

from ..common.db_connection import DbConnection
from ..common.db_cursor import DbCursor
from .mssql_proxy_cursor import MSSQLProxyCursor


class MSSQLProxyConnection(DbConnection):
    """
    DB-API 2.0 compliant connection interface for ``mssql_python``.
    """

    __connection: Connection

    def __init__(self, provider_connection: Connection) -> None:
        """
        Initialize a new MSSQLProxyConnection.

        :param provider_connection: A raw mssql_python Connection instance.
        """
        self.__connection = provider_connection

    @property
    def mssql_connection(self) -> Connection:
        """
        Access the underlying raw mssql_python connection.

        :returns: The :class:`mssql_python.Connection` instance.
        """
        return self.__connection

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        """
        Create a new cursor for executing SQL statements.

        :returns: A :class:`MSSQLProxyCursor` instance.
        """
        return MSSQLProxyCursor(self.__connection.cursor(*args, **kwargs))

    def commit(self) -> None:
        """Commit the current transaction."""
        self.__connection.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.__connection.rollback()

    def close(self) -> None:
        """Close the database connection."""
        self.__connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /
    ) -> Literal[False]:
        self.__connection.__exit__(exc_type, exc, tb)  # type: ignore[arg-type]
        return False


__all__ = ['MSSQLProxyConnection']
