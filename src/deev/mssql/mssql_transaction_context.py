# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from contextvars import ContextVar
import logging
import mssql_python
from mssql_python import Connection
from types import TracebackType
from typing import Any, Generator, Literal, Self, cast
from uuid import uuid4

import hanaro

from ..common.db_connection import DbConnection
from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_transaction_context import DbTransactionContext
from ..common.tlc_parser import extract_begin_name, extract_rollback_name, extract_savepoint_name
from .mssql_proxy_connection import MSSQLProxyConnection


class MSSQLTransactionContext(DbTransactionContext):
    """
    Transaction context for Microsoft SQL Server that manages transaction state.
    """

    __ambient_transaction_id: ContextVar[str | None] = ContextVar[str | None]('ambient_transaction_id', default=None)
    __context: DbContext | None
    __cursor: DbCursor | None
    __logger: logging.Logger
    __savepoints: list[str]
    __transaction_depth: int
    __transaction_id: str
    __transaction_name: str | None

    def __init__(self, context: DbContext, *, owns_context: bool | None = None):
        """
        Initialize a new MSSQLTransactionContext.

        :param context: A :class:`DbContext` or :class:`MSSQLProxyConnection` instance.
        """
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (MSSQLProxyConnection, MSSQLTransactionContext))
        self.__context = context if self.__is_deev_context else MSSQLProxyConnection(context)  # type: ignore[arg-type]
        self.__logger = hanaro.get_logger()
        self.__transaction_id = uuid4().hex
        self.__transaction_depth = 0
        self.__savepoints: list[str] = []
        self.__transaction_name: str | None = None
        self.__cursor = None

    def __del__(self):
        self.close()

    def __enter__(self) -> Self:
        """
        Begin a transaction when entering the context manager.

        :returns: This transaction context instance.
        """
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

        :param sql: The raw SQL statement to inspect.
        :returns: The SQL to execute, or None to scrub it.
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
                name_token = extract_begin_name(sql)
                # Strip brackets from name (e.g., [my_txn] → MY_TXN)
                if name_token and name_token.startswith('[') and name_token.endswith(']'):
                    name_token = name_token[1:-1]
                self.__transaction_name = name_token
                self.__ambient_transaction_id.set(self.__transaction_name or self.__transaction_id)
            return sql

        elif prefix == 'SAVE':
            name_token = extract_savepoint_name(sql)
            if name_token:
                if name_token.startswith('[') and name_token.endswith(']'):
                    name_token = name_token[1:-1]
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

        elif prefix == 'ROLL':
            if self.__transaction_depth == 0:
                raise DbError('No active transaction to rollback.')
            name = extract_rollback_name(sql)

            if name:
                if name.startswith('[') and name.endswith(']'):
                    name = name[1:-1]
                if name in self.__savepoints:
                    # Savepoint rollback - pop savepoints but don't reset depth
                    while self.__savepoints:
                        sp = self.__savepoints.pop()
                        if sp == name:
                            break
                    return 'ROLLBACK TRANSACTION ' + (name or '')
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
            return 'ROLLBACK TRANSACTION'

        return sql

    @property
    def connection(self) -> DbConnection:
        """
        Get the underlying database connection.

        :returns: The :class:`DbConnection` instance.
        """
        if isinstance(self.__context, DbTransactionContext):
            return cast(DbTransactionContext, self.__context).connection
        else:
            return cast(DbConnection, self.__context)

    @property
    def transaction_name(self) -> str | None:
        """Return the name of the outermost transaction."""
        return self.__transaction_name

    @property
    def savepoints(self) -> tuple[str, ...]:
        """Return the savepoint list as a tuple."""
        return tuple(self.__savepoints)

    def begin_transaction(self, name: str | None = None) -> Self:
        """
        Begin a new database transaction.

        :param name: Optional transaction name. When depth is 0 and a name is
            provided, it is used to identify the transaction for targeted
            rollbacks. When depth is > 0, the name is ignored.
        :returns: This transaction context instance.
        """
        sql = 'BEGIN TRANSACTION'
        if name:
            sql += f' {name}'
        self.execute(sql)
        return self

    def create_savepoint(self, name: str | None = None) -> Self:
        """
        Create a savepoint within the current transaction.

        Savepoint names are limited to 30 characters (TSQL identifier limit).
        Savepoints are tracked in LIFO order for rollback.

        :param name: Optional explicit savepoint name. When not
            provided, an auto-generated name is used.
        :returns: This transaction context instance.
        """
        if name is None:
            name = f'TID_{uuid4().hex[:24]}'  # 4 + 24 = 28 chars
        sql = f'SAVE TRANSACTION {name}'
        self.execute(sql)
        return self

    def rollback_savepoint(self, name: str | None = None) -> None:
        """
        Rollback to the most recently saved savepoint, or to a specific one
        if ``name`` is provided.

        If ``name`` is not provided, the most-recently created
        savepoint (top of ``__savepoints``) is used.

        If no savepoints exist when called with no name, this is a no-op.

        If a savepoint was implicitly released by DDL, this logs a warning
        and continues. Does NOT invalidate the entire transaction.

        Note: ``__preprocess_sql`` always removes the named
        savepoint (and everything above it) from ``__savepoints`` regardless
        of whether the DB-side rollback succeeded. This means if a savepoint
        was released by DDL and the user calls ``rollback_savepoint`` against
        it, the list is cleaned up silently to prevent repeated failed
        attempts. The trade-off is that the tracking list may diverge from
        the actual DB state in error scenarios.

        :param name: Optional explicit savepoint name.
        """
        if name is None:
            if not self.__savepoints:
                return
            name = self.__savepoints[-1]
        sql = f'ROLLBACK TRANSACTION {name}'
        try:
            self.execute(sql)
        except Exception:
            self.__logger.warning(f'Savepoint {name} already released')

    def close(self) -> None:
        """Close method for cross-compatibility with :class:`DbConnection`."""
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
        """
        Commit the current transaction.

        Commits all savepoints implicitly (MSSQL behavior).
        When depth reaches 0, ``__transaction_name`` and the ambient
        transaction ID are cleared.
        :raises DbError: If the transaction has already been committed or rolled back.
        """
        self.execute('COMMIT')

    def cursor(self) -> DbCursor:
        """
        Create a new cursor for executing SQL statements.

        :returns: A :class:`DbCursor` instance.
        """
        assert self.__context is not None, 'no context'
        return self.__context.cursor()

    def execute(self, sql: str, parameters: DbParameters | None = None, raw: bool | None = False) -> DbCursor:
        """
        Execute a SQL statement.

        :param sql: A string containing the SQL statement to execute.
        :param parameters: A tuple containing the parameters to substitute into the SQL statement.
        :param raw: If True, bypasses preprocessing and executes SQL as-is.
        :return: The cursor object the caller can use to retrieve results.
        :raises DbError: If the transaction has already been committed or rolled back.
        """
        if not raw:
            modified = self.__preprocess_sql(sql)
            if modified is None:
                from ..common.noop_cursor import NoopCursor
                return NoopCursor()
            sql = modified
        assert self.__context is not None, 'no context'
        if self.__cursor is None:
            self.__cursor = self.__context.cursor()
        if parameters is None:
            self.__cursor.execute(sql)
        else:
            self.__cursor.execute(sql, tuple(parameters))
        if sql == 'COMMIT' and self.__transaction_depth == -2:
            if isinstance(self.__context, MSSQLProxyConnection):
                self.__context.mssql_connection.commit()
        return self.__cursor

    def execute_nonquery(self, sql: str, parameters: DbParameters | None = None) -> None:
        """
        Execute a SQL statement that does not return rows.

        :param sql: The SQL statement to execute.
        :param parameters: Optional parameters for the statement.
        :raises DbError: If the transaction has already been committed or rolled back.
        """
        self.execute(sql, parameters)

    def execute_reader(self, sql: str, parameters: DbParameters | None = None) -> Generator[Any, None, None]:
        """
        Execute a SQL statement that returns a result set.

        :param sql: The SQL statement to execute.
        :param parameters: Optional parameters for the statement.
        :yields: Rows from the result set.
        :raises DbError: If the transaction has already been committed or rolled back.
        """
        cursor = self.execute(sql, parameters)
        row = cursor.fetchone()
        while row is not None:
            yield row
            row = cursor.fetchone()

    def execute_scalar(self, sql: str, parameters: DbParameters | None = None) -> Any:
        """
        Execute a SQL statement and return a single value.

        :param sql: The SQL statement to execute.
        :param parameters: Optional parameters for the statement.
        :returns: The first column of the first row, or the row count on error.
        :raises DbError: If the transaction has already been committed or rolled back.
        """
        cursor = self.execute(sql, parameters)
        try:
            row = cursor.fetchone()
            return None if row is None else row[0]
        except (mssql_python.ProgrammingError, mssql_python.InterfaceError):
            return cursor.rowcount

    def execute_script(self, sql: str, raw: bool = False) -> None:
        """
        Execute a SQL script containing multiple statements.

        :param sql: The SQL script to execute.
        :param raw: If True, bypasses preprocessing and line splitting;
            calls execute(raw=True) directly.
        """
        if raw is True:
            self.execute(sql, raw=True)
            return
        lines = sql.split('\n')
        scrubbed = [line for line in lines if self.__preprocess_sql(line) is not None]
        joined = '\n'.join(scrubbed)
        if joined:
            self.execute(joined, raw=True)

    def rollback(self, name: str | None = None) -> None:
        """
        Rollback the entire transaction (invalidates everything).

        This is a FULL rollback — all savepoints are also invalidated.
        ``__transaction_depth`` is reset to 0.
        ``__savepoints`` is cleared.

        :param name: Optional savepoint or transaction name. When provided,
            constructs ``ROLLBACK TRANSACTION {name}``. When None, constructs
            ``ROLLBACK TRANSACTION``.
        :raises DbError: If the transaction has already been committed or rolled back,
            or the name is invalid.
        """
        sql = 'ROLLBACK' if name is None else f'ROLLBACK TRANSACTION {name}'
        self.execute(sql)


__all__ = ['MSSQLTransactionContext']
