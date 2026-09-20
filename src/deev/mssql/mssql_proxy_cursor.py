# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging
from mssql_python import Cursor
from typing import (
    Any,
    Sequence,
    cast,
)

from ..common.db_cursor import DbCursor, DbCursorDescription
from ..common.db_parameters import DbParameters


class MSSQLProxyCursor(DbCursor):
    """
    Normalized cursor interface for mssql_python.

    Ensures features are preserved whenever a cursor is acquired via ``deev``.
    Substitutes ``%?`` placeholders (deev's canonical param style) with ``?``
    (mssql_python's expected parameter style).
    """

    __cursor: Cursor
    __logger: logging.Logger
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: Cursor) -> None:
        """
        Initialize a new MSSQLProxyCursor.

        :param provider_cursor: A raw mssql_python Cursor instance.
        """
        self.__cursor = provider_cursor
        self.__logger = hanaro.get_logger()
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'

    @property
    def description(self) -> DbCursorDescription:
        """
        Get the result description of the last executed statement.

        :returns: A sequence of tuples describing result columns, or ``None``.
        """
        return cast(DbCursorDescription, self.__cursor.description)

    @property
    def rowcount(self) -> int:
        """
        Get the number of rows affected by the last executed statement.

        :returns: The number of affected rows.
        """
        return self.__cursor.rowcount

    def execute(self, operation: str, parameters: DbParameters | None = None) -> None:
        """
        Execute a SQL operation with optional parameters.

        Substitutes ``%?`` placeholders with ``?`` before execution.

        :param operation: The SQL statement to execute.
        :param parameters: Optional parameters to bind to the statement.
        """
        if parameters is None or len(parameters) == 0:
            self.__cursor.execute(operation)
        else:
            operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
            self.__cursor.execute(operation, parameters)  # type: ignore[arg-type]

    def executemany(self, operation: str, seq_of_parameters: Sequence[DbParameters]) -> None:
        """
        Execute a SQL operation against multiple parameter sequences.

        Substitutes ``%?`` placeholders with ``?`` before execution.

        :param operation: The SQL statement to execute.
        :param seq_of_parameters: A sequence of parameter dictionaries.
        """
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.executemany(operation, [tuple(p) if isinstance(p, (tuple, list)) else dict(p) for p in seq_of_parameters])  # type: ignore[arg-type]

    def fetchone(self) -> tuple[Any, ...] | None:
        """
        Fetch the next row of a query result set.

        :returns: A tuple representing a single row, or ``None`` when no more data is available.
        """
        return cast(tuple[Any, ...] | None, self.__cursor.fetchone())

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        """
        Fetch the next set of rows of a query result set.

        :param size: The number of rows to fetch.
        :returns: A list of tuples representing the fetched rows.
        """
        return cast(list[tuple[Any, ...]], self.__cursor.fetchmany(size=size))

    def fetchall(self) -> list[tuple[Any, ...]]:
        """
        Fetch all remaining rows of a query result set.

        :returns: A list of tuples representing all remaining rows.
        """
        return cast(list[tuple[Any, ...]], self.__cursor.fetchall())

    def close(self) -> None:
        """Close the cursor."""
        self.__cursor.close()


__all__ = ['MSSQLProxyCursor']
