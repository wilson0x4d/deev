# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging
from mysql.connector.abstracts import MySQLCursorAbstract
from typing import (
    Any,
    Optional,
    Sequence
)

from ..common.db_cursor import DbCursor
from ..common.db_params import DbParams


class MysqlProxyCursor(DbCursor):
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
    def description(self) -> Optional[Sequence[tuple[Any, ...]]]:
        return self.__cursor.description

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    def execute(self, operation: str, params: Optional[DbParams] = None) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__logger.debug(f'execute({operation!r}, {params!r})')
        if params is None:
            self.__cursor.execute(operation)
        else:
            self.__cursor.execute(operation, params)  # type: ignore[arg-type]

    def executemany(self, operation: str, seq_params: Sequence[DbParams]) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__logger.debug(f'execute({operation!r}, {seq_params!r})')
        self.__cursor.executemany(operation, seq_params)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.__cursor.fetchone()  # type: ignore[return-value]

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchmany(size=size)  # type: ignore[return-value]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchall()  # type: ignore[return-value]

    def close(self) -> None:
        self.__cursor.close()


__all__ = ['MysqlProxyCursor']
