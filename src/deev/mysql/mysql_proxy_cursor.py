# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging
from mysql.connector.abstracts import MySQLCursorAbstract
from typing import (
    Any,
    Sequence
)

from ..common.db_cursor import DbCursor, DbCursorDescription
from ..common.db_parameters import DbParameters


class MySQLProxyCursor(DbCursor):
    """
    Normalized cursor interface for MySQL Connector.

    Ensures features are preserved whenever a cursor is acquired via ``deev``.
    """
    __cursor: MySQLCursorAbstract
    __logger: logging.Logger
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: MySQLCursorAbstract) -> None:
        self.__cursor = provider_cursor
        self.__logger = hanaro.get_logger()
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '%s'

    @property
    def description(self) -> DbCursorDescription:
        return self.__cursor.description  # type: ignore[return-value]

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    def execute(self, operation: str, parameters: DbParameters | None = None) -> None:
        if parameters is None or len(parameters) == 0:
            self.__cursor.execute(operation)
        else:
            operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
            self.__cursor.execute(operation, parameters)  # type: ignore[arg-type]

    def executemany(self, operation: str, seq_of_parameters: Sequence[DbParameters]) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.executemany(operation, seq_of_parameters)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.__cursor.fetchone()  # type: ignore[return-value]

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchmany(size=size)  # type: ignore[return-value]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchall()  # type: ignore[return-value]

    def close(self) -> None:
        self.__cursor.close()


__all__ = ['MySQLProxyCursor']
