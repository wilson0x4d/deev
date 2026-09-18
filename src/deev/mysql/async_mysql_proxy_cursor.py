# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging
from mysql.connector.aio import cursor as aio_cursor
from typing import (
    Any,
    Sequence
)

from ..common.async_db_cursor import AsyncDbCursor, AsyncDbCursorDescription
from ..common.db_parameters import DbParameters


class AsyncMySQLProxyCursor(AsyncDbCursor):
    """
    Async DB-API 2.0 compliant cursor interface for mysql.connector.aio.
    """
    __cursor: aio_cursor.MySQLCursorAbstract
    __logger: logging.Logger
    __sql_arg_expect: str
    __sql_arg_subst: str

    def __init__(self, provider_cursor: aio_cursor.MySQLCursorAbstract) -> None:
        self.__cursor = provider_cursor
        self.__logger = hanaro.get_logger()
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '%s'

    @property
    def description(self) -> AsyncDbCursorDescription:
        return self.__cursor.description  # type: ignore[return-value]

    @property
    def rowcount(self) -> int:
        return self.__cursor.rowcount

    async def execute(self, operation: str, parameters: DbParameters | None = None) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__logger.debug(f'execute({operation!r}, {parameters!r})')
        if parameters is None:
            await self.__cursor.execute(operation)
        else:
            await self.__cursor.execute(operation, parameters)  # type: ignore[arg-type]

    async def executemany(self, operation: str, seq_of_parameters: Sequence[DbParameters]) -> None:
        operation = operation.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__logger.debug(f'execute({operation!r}, {seq_of_parameters!r})')
        await self.__cursor.executemany(operation, seq_of_parameters)  # type: ignore[arg-type]

    async def fetchone(self) -> tuple[Any, ...] | None:
        return await self.__cursor.fetchone()  # type: ignore[return-value]

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return await self.__cursor.fetchmany(size)  # type: ignore[return-value]

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return await self.__cursor.fetchall()  # type: ignore[return-value]

    async def close(self) -> None:
        await self.__cursor.close()


__all__ = ['AsyncMySQLProxyCursor']
