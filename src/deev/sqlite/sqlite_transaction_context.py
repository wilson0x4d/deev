# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from contextvars import ContextVar
from types import TracebackType
from typing import Any, Generator, Literal, Self, cast
from uuid import uuid4

from ..common.db_connection import DbConnection
from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_transaction_context import DbTransactionContext
from ..common.tlc_parser import extract_begin_name, extract_rollback_name, extract_savepoint_name, is_rollback_to
from .sqlite_proxy_connection import SQLiteProxyConnection


class SQLiteTransactionContext(DbTransactionContext):

    __ambient_transaction_id: ContextVar[str | None] = ContextVar[str | None]('ambient_transaction_id', default=None)
    __context: DbContext | None
    __cursor: DbCursor | None
    __savepoints: list[str]
    __sql_arg_expect: str
    __sql_arg_subst: str
    __transaction_depth: int
    __transaction_id: str
    __transaction_name: str | None

    def __init__(self, context: DbContext, *, owns_context: bool | None = None):
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (SQLiteProxyConnection, SQLiteTransactionContext))
        self.__context = context if self.__is_deev_context else SQLiteProxyConnection(context)  # type: ignore[arg-type]
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'
        self.__transaction_id = uuid4().hex
        self.__transaction_depth = 0
        self.__savepoints: list[str] = []
        self.__transaction_name: str | None = None
        self.__cursor = None

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
            if self.__transaction_depth == 1:
                self.__transaction_name = extract_begin_name(sql)
                self.__ambient_transaction_id.set(self.__transaction_name or self.__transaction_id)
            else:
                return None
            return sql

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
            is_savepoint_rollback = is_rollback_to(sql)

            if name:
                if name in self.__savepoints:
                    while self.__savepoints:
                        sp = self.__savepoints.pop()
                        if sp == name:
                            break
                elif name == self.__transaction_name:
                    pass  # full rollback, depth reset below
                else:
                    raise DbError('Invalid Transaction Name')
            else:
                pass  # full rollback, depth reset below

            if is_savepoint_rollback:
                return 'ROLLBACK TO SAVEPOINT ' + (name or '')
            else:
                self.__transaction_depth = -3
                self.__savepoints.clear()
                self.__transaction_name = None
                self.__ambient_transaction_id.set(None)
                return 'ROLLBACK TRANSACTION'

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
        sql = 'BEGIN TRANSACTION' if name is None else f'BEGIN TRANSACTION {name}'
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
        assert self.__context is not None, 'no context'
        return self.__context.cursor()

    def execute(self, sql: str, parameters: DbParameters | None = None, raw: bool | None = False) -> DbCursor:
        if not raw:
            modified = self.__preprocess_sql(sql)
            if modified is None:
                from ..common.noop_cursor import NoopCursor
                return NoopCursor()
            sql = modified
        sql = sql.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        assert self.__context is not None, 'no context'
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        self.__cursor.execute(
            sql,
            tuple(parameters) if parameters is not None else tuple())
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
        except sqlite3.ProgrammingError:
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


__all__ = ['SQLiteTransactionContext']
