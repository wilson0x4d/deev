# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from contextvars import ContextVar
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generator, Literal, Self, cast

import hanaro
from uuid import uuid4, UUID

from ..common.db_connection import DbConnection
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_params import DbParams
from ..common.db_transaction_context import DbTransactionContext
from .clickhouse_proxy_connection import ClickHouseProxyConnection

if TYPE_CHECKING:
    from ..common.db_context import DbContext


class ClickHouseTransactionContext(DbTransactionContext):
    """
    Transaction context for ClickHouse.

    ClickHouse does not support traditional ACID transactions. All transaction methods are
    no-ops. This context enables using ClickHouse connections with code that expects
    transactional semantics.  For example, when swapping providers.
    """

    __ambient_transaction_id: ContextVar = ContextVar('ambient_transaction_id', default=None)
    __context: DbContext
    __cursor: DbCursor | None
    __logger: logging.Logger
    __transaction_id: UUID
    __transaction_state: int

    def __init__(self, context: DbContext) -> None:
        self.__context = context if isinstance(context, (ClickHouseProxyConnection, ClickHouseTransactionContext)) else ClickHouseProxyConnection(context)  # type: ignore[arg-type]
        self.__logger = hanaro.get_logger()
        self.__transaction_id = uuid4()
        self.__transaction_state = 0
        self.__cursor = None

    def __del__(self) -> None:
        try:
            if self.__cursor is not None:
                self.__cursor.close()
        except Exception:
            pass

    def __enter__(self) -> Self:
        self.begin_transaction()
        return self

    def __exit__(self, exc_type: type[BaseException] | None = None, exc_value: BaseException | None = None, traceback: TracebackType | None = None) -> Literal[False]:
        return False

    def __update_transaction_state(self, sql: str) -> None:
        sql = sql.lstrip().upper()
        prefix = sql.strip()[:4]
        if prefix in ['CREA', 'DELE', 'DROP', 'INSE', 'UPDA', 'ALTE', 'ALT']:
            self.__transaction_state = 2
        elif prefix in ['COMM', 'ROLL']:
            self.__transaction_state = 3
            if ClickHouseTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
                ClickHouseTransactionContext.__ambient_transaction_id.set(None)
        elif self.__transaction_state == 0:
            self.__transaction_state = 1

    @property
    def connection(self) -> DbConnection:
        if isinstance(self.__context, DbTransactionContext):
            return cast(DbTransactionContext, self.__context).connection
        else:
            return cast(DbConnection, self.__context)

    @property
    def clickhouse_client(self) -> Any:
        return cast(ClickHouseProxyConnection, self.__context).clickhouse_client

    def begin_transaction(self) -> DbTransactionContext:
        if self.__transaction_state != 0:
            raise DbError(f'A transaction was already started in this context, cannot begin a new transaction. ({self.__transaction_state})')
        self.__transaction_state = 1
        self.__cursor = self.__context.cursor()
        if ClickHouseTransactionContext.__ambient_transaction_id.get(None) is None:
            ClickHouseTransactionContext.__ambient_transaction_id.set(self.__transaction_id)
        return self

    def close(self) -> None:
        pass

    def commit(self) -> None:
        try:
            self.__context.commit()
        except Exception:
            pass
        self.__update_transaction_state('COMMIT')

    def cursor(self) -> DbCursor:
        return self.__context.cursor()

    def execute(self, sql: str, params: DbParams | None = None) -> DbCursor:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(sql, params)
        return cast(DbCursor, self.__cursor)

    def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)

    def execute_reader(self, sql: str, params: DbParams | None = None) -> Generator[Any, None, None]:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)
        row = self.__cursor.fetchone()
        while row is not None:
            yield row
            row = self.__cursor.fetchone()

    def execute_scalar(self, sql: str, params: DbParams | None = None) -> Any:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)
        row = self.__cursor.fetchone()
        return None if row is None else row[0]

    def execute_script(self, sql: str) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state("INSERT")
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(sql)

    def rollback(self) -> None:
        try:
            self.__context.rollback()
        except Exception:
            pass
        self.__update_transaction_state('ROLLBACK')


__all__ = ['ClickHouseTransactionContext']
