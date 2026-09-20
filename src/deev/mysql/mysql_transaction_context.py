# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from contextvars import ContextVar
import hanaro
import logging
import mysql.connector
from types import TracebackType
from typing import Any, Generator, Literal, Self, cast
from uuid import uuid4

from ..common.db_connection import DbConnection
from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_transaction_context import DbTransactionContext
from ..common.tlc_parser import extract_begin_name, extract_rollback_name, extract_savepoint_name, extract_start_name
from .mysql_proxy_connection import MySQLProxyConnection


class MySQLTransactionContext(DbTransactionContext):

    __ambient_transaction_id: ContextVar[str | None] = ContextVar[str | None]('ambient_transaction_id', default=None)
    __context: DbContext | None
    __cursor: DbCursor | None
    __logger: logging.Logger
    __savepoints: list[str]
    __transaction_depth: int
    __transaction_id: str
    __transaction_name: str | None

    def __init__(self, context: DbContext, *, owns_context: bool | None = None):
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (MySQLProxyConnection, MySQLTransactionContext))
        self.__context = context if self.__is_deev_context else MySQLProxyConnection(context)  # type: ignore[arg-type]
        self.__logger = hanaro.get_logger()
        self.__transaction_id = uuid4().hex
        self.__transaction_depth = 0
        self.__savepoints: list[str] = []
        self.__transaction_name: str | None = None
        self.__cursor: DbCursor | None = None

    def __del__(self):
        self.close()

    def __enter__(self) -> Self:
        self.begin_transaction()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> Literal[False]:
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

        For non-TLC statements: returns SQL unchanged.

        For TLC keywords: updates internal state (depth, savepoints, transaction
        name) and returns:
          - Modified SQL if the DBMS supports this operation at the current depth.
          - None if scrubbed because the DBMS does not support it.
          - Raises DbError if operation is invalid.

        MySQL-specific: strips name from START TRANSACTION (MySQL doesn't support named transactions).
        """
        if self.__transaction_depth == -1:
            raise DbError('Cannot use a transaction context that has exited.')
        elif self.__transaction_depth == -2:
            raise DbError('Cannot use a transaction context that has been committed.')
        elif self.__transaction_depth == -3:
            raise DbError('Cannot use a transaction context that has been rolled back.')

        sql_upper = sql.lstrip().upper()
        prefix = sql_upper[:4]

        if prefix == 'BEGI' or prefix == 'STAR':
            if self.__transaction_depth > 0:
                return None
            self.__transaction_depth += 1
            if prefix == 'STAR':
                self.__transaction_name = extract_start_name(sql)
            elif sql_upper.startswith('BEGIN WORK') or sql_upper.startswith('BEGIN '):
                self.__transaction_name = None
            else:
                self.__transaction_name = extract_begin_name(sql)
            self.__ambient_transaction_id.set(self.__transaction_name or self.__transaction_id)
            return 'START TRANSACTION'

        elif prefix == 'SAVE' or sql_upper.startswith('SAVEPOINT '):
            name_token = extract_savepoint_name(sql)
            if name_token:
                self.__savepoints.append(name_token)
            return sql

        elif prefix == 'COMM':
            if self.__transaction_depth == 0:
                raise DbError('No active transaction to commit.')
            self.__transaction_depth -= 1
            if self.__transaction_depth == 0:
                self.__savepoints.clear()
                self.__transaction_name = None
                self.__ambient_transaction_id.set(None)
                self.__transaction_depth = -2
                return 'COMMIT'
            else:
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
                    return f'ROLLBACK TO SAVEPOINT {name}'
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
            return 'ROLLBACK'

        return sql

    @property
    def connection(self) -> DbConnection:
        if isinstance(self.__context, DbTransactionContext):
            return cast(DbTransactionContext, self.__context).connection
        else:
            return cast(DbConnection, self.__context)

    @property
    def transaction_name(self) -> str | None:
        return self.__transaction_name

    @property
    def savepoints(self) -> tuple[str, ...]:
        return tuple(self.__savepoints)

    def begin_transaction(self, name: str | None = None) -> Self:
        sql = 'START TRANSACTION' if name is None else f'START TRANSACTION {name}'
        self.execute(sql)
        return self

    def create_savepoint(self, name: str | None = None) -> Self:
        if name is None:
            name = f'TID_{uuid4().hex[:24]}'
        sql = f'SAVEPOINT {name}'
        self.execute(sql)
        return self

    def rollback_savepoint(self, name: str | None = None) -> None:
        if name is None:
            if not self.__savepoints:
                return
            name = self.__savepoints[-1]
        sql = f'ROLLBACK TO SAVEPOINT {name}'
        self.execute(sql)

    def close(self) -> None:
        try:
            if self.__cursor is not None:
                self.__cursor.close()
                self.__cursor = None
        except Exception:
            pass
        try:
            if self.__context is not None and self.__owns_context and hasattr(self.__context, 'close'):
                self.__context.close()
                self.__context = None
        except Exception:
            pass

    def commit(self) -> None:
        self.execute('COMMIT')

    def cursor(self) -> DbCursor:
        assert self.__context is not None, 'context expected'
        return self.__context.cursor()

    def execute(self, sql: str, params: DbParameters | None = None, raw: bool = False) -> DbCursor:
        if not raw:
            modified = self.__preprocess_sql(sql)
            if modified is None:
                from ..common.noop_cursor import NoopCursor
                return NoopCursor()
            sql = modified
        assert self.__context is not None, 'context expected'
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        return cast(DbCursor, self.__cursor)

    def execute_nonquery(self, sql: str, params: DbParameters | None = None) -> None:
        self.execute(sql, params)

    def execute_reader(self, sql: str, params: DbParameters | None = None) -> Generator[Any, None, None]:
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        while row is not None:
            yield row
            row = cursor.fetchone()

    def execute_scalar(self, sql: str, params: DbParameters | None = None) -> Any:
        cursor = self.execute(sql, params)
        try:
            row = cursor.fetchone()
            return None if row is None else row[0]
        except mysql.connector.ProgrammingError:
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


__all__ = ['MySQLTransactionContext']
