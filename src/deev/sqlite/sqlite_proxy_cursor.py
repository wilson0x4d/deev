# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging
from sqlite3 import Cursor
from typing import (
    Any,
    Sequence
)

from ..common.db_cursor import DbCursor
from ..common.db_params import DbParams


class SqliteProxyCursor(DbCursor):
    """
    Normalized cursor interface for sqlite3.

    Ensures features are preserved whenever a cursor is acquired via ``deev``.
    """
    __cursor: Cursor
    __logger: logging.Logger
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: Cursor) -> None:
        self.__cursor = provider_cursor
        self.__logger = hanaro.get_logger()
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'

    @property
    def description(self) -> Sequence[tuple[Any, ...]] | None:
        return self.__cursor.description

    @property
    def lastrowid(self) -> int | None:
        return self.__cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    def execute(self, operation: str, params: DbParams | None = None) -> None:
        if params is not None:
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
        return self.__cursor.fetchone()

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchmany(size=size)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.__cursor.fetchall()

    def close(self) -> None:
        self.__cursor.close()


__all__ = ['SqliteProxyCursor']
