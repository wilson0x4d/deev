# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from contextvars import ContextVar
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generator, Literal, Self, cast

import hanaro
from uuid import uuid4

from ..common.db_connection import DbConnection
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_transaction_context import DbTransactionContext
from ..common.tlc_parser import extract_begin_name, extract_rollback_name, extract_savepoint_name
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

    __ambient_transaction_id: ContextVar[str | None] = ContextVar[str | None]('ambient_transaction_id', default=None)
    __context: DbContext | None
    __cursor: DbCursor | None
    __logger: logging.Logger
    __savepoints: list[str]
    __transaction_depth: int
    __transaction_id: str
    __transaction_name: str | None

    def __init__(self, context: DbContext, *, owns_context: bool | None = None) -> None:
        """
        Initialize the ClickHouse transaction context.

        ClickHouse does not support traditional ACID transactions; all transaction methods
        are no-ops. This context enables using ClickHouse with code that expects
        transactional semantics.

        :param context: A :class:`ClickHouseProxyConnection` or related context.
        :param owns_context: Whether this transaction context owns *context* and should close it.
        """
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (ClickHouseProxyConnection, ClickHouseTransactionContext))
        self.__context = context if self.__is_deev_context else ClickHouseProxyConnection(context)  # type: ignore[arg-type]
        self.__logger = hanaro.get_logger()
        self.__transaction_id = uuid4().hex
        self.__transaction_depth = 0
        self.__savepoints: list[str] = []
        self.__transaction_name: str | None = None
        self.__cursor = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> Self:
        self.begin_transaction()
        return self

    def __exit__(self, exc_type: type[BaseException] | None = None, exc_value: BaseException | None = None, traceback: TracebackType | None = None) -> Literal[False]:
        try:
            if self.__transaction_depth > 0:
                if exc_type is not None:
                    self.rollback()
                else:
                    self.rollback()
                    raise DbError('Detected uncommitted transaction, rolling back. You must explicitly call commit or rollback.')
        finally:
            self.close()
            self.__transaction_depth = -1
            self.__ambient_transaction_id.set(None)
        return False

    def __preprocess_sql(self, sql: str) -> str | None:
        """
        Parse SQL to determine whether it is a transaction-control (TLC) keyword
        or a regular SQL statement.

        For ClickHouse: all TLC keywords return None (scrubbed) since ClickHouse
        has no transaction support. Depth tracking is for diagnostics/consistency.
        """
        if self.__transaction_depth == -1:
            raise DbError('Cannot use a transaction context that has exited.')
        elif self.__transaction_depth == -2:
            raise DbError('Cannot use a transaction context that has been committed.')
        elif self.__transaction_depth == -3:
            raise DbError('Cannot use a transaction context that has been rolled back.')

        sql_upper = sql.lstrip().upper()
        prefix = sql_upper[:4]

        if prefix == 'BEGI':
            self.__transaction_depth += 1
            self.__transaction_name = extract_begin_name(sql)
            return None

        elif prefix == 'SAVE' or sql_upper.startswith('SAVEPOINT '):
            name_token = extract_savepoint_name(sql)
            if name_token:
                self.__savepoints.append(name_token)
            return None

        elif prefix == 'COMM':
            if self.__transaction_depth == 0:
                raise DbError('No active transaction to commit.')
            self.__transaction_depth -= 1
            if self.__transaction_depth == 0:
                self.__savepoints.clear()
                self.__transaction_name = None
                self.__ambient_transaction_id.set(None)
                self.__transaction_depth = -2
            return None

        elif prefix == 'ROLL':
            if self.__transaction_depth == 0:
                raise DbError('Cannot rollback, no transaction.')
            name = extract_rollback_name(sql)

            if name:
                if name in self.__savepoints:
                    while self.__savepoints:
                        sp = self.__savepoints.pop()
                        if sp == name:
                            break
                    return None
                elif name == self.__transaction_name:
                    pass  # full rollback, depth reset below
                else:
                    raise DbError('Invalid Transaction Name')
            else:
                pass  # full rollback, depth reset below

            self.__transaction_depth = -3
            self.__savepoints.clear()
            self.__transaction_name = None
            self.__ambient_transaction_id.set(None)
            return None

        return sql

    @property
    def connection(self) -> DbConnection:
        if isinstance(self.__context, DbTransactionContext):
            return cast(DbTransactionContext, self.__context).connection
        else:
            return cast(DbConnection, self.__context)

    @property
    def clickhouse_client(self) -> Any:
        return cast(ClickHouseProxyConnection, self.__context).clickhouse_client

    @property
    def transaction_name(self) -> str | None:
        return self.__transaction_name

    @property
    def savepoints(self) -> tuple[str, ...]:
        return tuple(self.__savepoints)

    def begin_transaction(self, name: str | None = None) -> Self:
        if self.__cursor is None:
            assert self.__context is not None, 'no context'
            self.__cursor = self.__context.cursor()
        sql = 'BEGIN TRANSACTION'
        if name:
            sql += f' {name}'
        self.execute(sql)
        return self

    def create_savepoint(self, name: str | None = None) -> Self:
        if name is None:
            name = f'TID_{uuid4().hex[:24]}'
        sql = f'SAVE TRANSACTION {name}'
        self.execute(sql)
        return self

    def rollback_savepoint(self, name: str | None = None) -> None:
        if name is None:
            if not self.__savepoints:
                return
            name = self.__savepoints[-1]
        sql = f'ROLLBACK TRANSACTION {name}'
        self.execute(sql)

    def close(self) -> None:
        try:
            if self.__cursor is not None:
                self.__cursor.close()
        except Exception:
            pass
        self.__cursor = None
        try:
            if self.__context is not None and self.__owns_context and hasattr(self.__context, 'close'):
                self.__context.close()
        except Exception:
            pass
        self.__context = None

    def commit(self) -> None:
        self.execute('COMMIT')

    def cursor(self) -> DbCursor:
        assert self.__context is not None, 'no context'
        return self.__context.cursor()

    def execute(self, sql: str, parameters: DbParameters | None = None, raw: bool = False) -> DbCursor:
        if not raw:
            modified = self.__preprocess_sql(sql)
            if modified is None:
                from ..common.noop_cursor import NoopCursor
                return NoopCursor()
            sql = modified
        if self.__cursor is None:
            assert self.__context is not None, 'no context'
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(sql, parameters)
        return cast(DbCursor, self.__cursor)

    def execute_nonquery(self, sql: str, parameters: DbParameters | None = None) -> None:
        self.execute(sql, parameters)

    def execute_reader(self, sql: str, parameters: DbParameters | None = None) -> Generator[Any, None, None]:
        cursor = self.execute(sql, parameters)
        row = cursor.fetchone()
        while row is not None:
            yield row
            row = cursor.fetchone()

    def execute_scalar(self, sql: str, parameters: DbParameters | None = None) -> Any:
        cursor = self.execute(sql, parameters)
        try:
            row = cursor.fetchone()
            return None if row is None else row[0]
        except Exception:
            return cursor.rowcount

    def execute_script(self, sql: str, raw: bool = False) -> None:
        if raw is True:
            self.execute(sql, raw=True)
            return
        lines = sql.split('\n')
        scrubbed = [line for line in lines if self.__preprocess_sql(line) is not None]
        joined = '\n'.join(scrubbed)
        if joined:
            self.execute(joined, raw=True)

    def rollback(self, name: str | None = None) -> None:
        sql = 'ROLLBACK' if name is None else f'ROLLBACK TRANSACTION {name}'
        self.execute(sql)


__all__ = ['ClickHouseTransactionContext']
