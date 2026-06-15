# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from contextvars import ContextVar
from types import TracebackType
from typing import Any, Generator, Literal, Optional, Self, cast
from uuid import UUID, uuid4

from ..common.DbConnection import DbConnection
from ..common.DbContext import DbContext
from ..common.DbCursor import DbCursor
from ..common.DbError import DbError
from ..common.DbParams import DbParams
from ..common.DbTransactionContext import DbTransactionContext
from .SqliteProxyConnection import SqliteProxyConnection


class SqliteTransactionContext(DbTransactionContext):

    __ambient_transaction_id: ContextVar = ContextVar('ambient_transacton_id', default=None)
    __transaction_id: UUID
    __context: DbContext
    __cursor: DbCursor
    __sql_arg_expect: str
    __sql_arg_subst: str
    __transaction_state: int

    def __init__(self, context: DbContext):
        self.__context = context if isinstance(context, (SqliteProxyConnection, SqliteTransactionContext)) else SqliteProxyConnection(context)  # type: ignore[arg-type]
        self.__sql_arg_expect = '%?'
        self.__sql_arg_subst = '?'
        self.__transaction_id = uuid4()
        self.__transaction_state = 0

    def __del__(self):
        try:
            if self.__cursor is not None:
                self.__cursor.close()
        except Exception:
            pass

    def __enter__(self) -> Self:
        self.begin_transaction()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,  # noqa: ARG001 - unused per context manager protocol
        traceback: Optional[TracebackType] = None
    ) -> Literal[False]:
        if exc_type is not None and self.__transaction_state == 2:
            self.rollback()
        elif self.__transaction_state == 2:
            self.rollback()
            raise DbError('Detected uncommitted transaction, rolling back. You must explicitly call commit or rollback.')
        elif self.__transaction_state <= 1:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        return False

    def __update_transaction_state(self, sql: str) -> None:
        sql = sql.lstrip().upper()
        prefix = sql.strip()[:4]
        if prefix in ['CREA', 'DELE', 'DROP', 'INSE', 'UPDA']:
            self.__transaction_state = 2
        elif prefix in ['COMM', 'ROLL']:
            self.__transaction_state = 3
            if SqliteTransactionContext.__ambient_transaction_id.get() == self.__transaction_id:
                SqliteTransactionContext.__ambient_transaction_id.set(None)
        elif self.__transaction_state == 0:
            self.__transaction_state = 1

    @property
    def connection(self) -> DbConnection:
        if isinstance(self.__context, DbTransactionContext):
            return cast(DbTransactionContext, self.__context).connection
        else:
            return cast(DbConnection, self.__context)

    def begin_transaction(self) -> DbTransactionContext:
        if self.__transaction_state != 0:
            raise DbError(f'A transaction was already started in this context, cannot begin a new transaction. ({self.__transaction_state})')
        self.__transaction_state = 1
        self.__cursor = self.__context.cursor()
        if SqliteTransactionContext.__ambient_transaction_id.get() is None:
            SqliteTransactionContext.__ambient_transaction_id.set(self.__transaction_id)
            self.__cursor.execute('BEGIN TRANSACTION')
        else:
            self.__cursor.execute(f'SAVEPOINT TID_{self.__transaction_id.hex};')
        return self

    def close(self) -> None:
        # only defined for cross-compat with `DbConnection`
        pass

    def commit(self) -> None:
        if SqliteTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            try:
                self.__cursor.execute('COMMIT')
            except sqlite3.OperationalError:
                # DDL implicitly committed and ended the transaction
                pass
        else:
            try:
                self.__cursor.execute(f'RELEASE SAVEPOINT TID_{self.__transaction_id.hex}')
            except sqlite3.OperationalError as e:
                if 'no such savepoint' in str(e):
                    # DDL implicitly committed all savepoints (SQLite behavior)
                    # Try COMMIT to end the ambient transaction; fall back to pass
                    try:
                        self.__cursor.execute('COMMIT')
                    except sqlite3.OperationalError:
                        # Also no active transaction — DDL killed it
                        pass
                else:
                    raise
        self.__update_transaction_state('COMMIT')

    def cursor(self) -> DbCursor:
        return self.__context.cursor()

    def execute(self, sql: str, params: Optional[DbParams] = None) -> DbCursor:
        """
        An `execute` method that more closely conforms to PEP 249.

        :param sql: A string containing the SQL statement to execute.
        :param params: A tuple containing the params to substitute into the SQL statement.
        :return: The cursor object the caller can use to retrieve results.
        """
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        sql = sql.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        return cast(DbCursor, self.__cursor)

    def execute_nonquery(self, sql: str, params: Optional[DbParams] = None) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        sql = sql.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        self.__update_transaction_state(sql)

    def execute_reader(self, sql: str, params: Optional[DbParams] = None) -> Generator[Any, None, None]:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        params = tuple(params) if params is not None else tuple()
        sql = sql.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.execute(sql, params)
        self.__update_transaction_state(sql)
        row = self.__cursor.fetchone()
        while row is not None:
            yield row
            row = self.__cursor.fetchone()

    def execute_scalar(self, sql: str, params: Optional[DbParams] = None) -> Any:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        sql = sql.replace(self.__sql_arg_expect, self.__sql_arg_subst)
        self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple()
        )
        self.__update_transaction_state(sql)
        row = self.__cursor.fetchone()
        return None if row is None else row[0]

    def execute_script(self, sql: str) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state("INSERT")
        self.__cursor.execute(sql)

    def rollback(self) -> None:
        if SqliteTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            self.__cursor.execute('ROLLBACK TRANSACTION')
        else:
            self.__cursor.execute(f'ROLLBACK TO SAVEPOINT TID_{self.__transaction_id.hex}')
        self.__update_transaction_state('ROLLBACK')


__all__ = ['SqliteTransactionContext']
