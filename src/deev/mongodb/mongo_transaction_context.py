# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from contextvars import ContextVar
import pymongo
from types import TracebackType
from typing import Any, Generator, Literal, Self, cast
from uuid import uuid4

from ..common.db_connection import DbConnection
from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_transaction_context import DbTransactionContext
from ..common.tlc_parser import extract_begin_name, extract_rollback_name, extract_savepoint_name
from .mongo_proxy_cursor import MongoProxyCursor


class MongoTransactionContext(DbTransactionContext):

    _DELEGATE_TXN_CACHE: dict[tuple[str | None, int], bool] = {}

    __ambient_transaction_id: ContextVar[str | None] = ContextVar[str | None]('ambient_transaction_id', default=None)
    __context: DbContext | None
    __cursor: DbCursor | None
    __database_name: str
    __savepoints: list[str]
    __transaction_depth: int
    __transaction_id: str
    __transaction_name: str | None
    __delegate_mode: bool | None

    def __init__(self, context: DbContext, *, owns_context: bool | None = None):
        """
        Initialize the MongoDB transaction context.

        :param context: A :class:`MongoProxyConnection` or related context.
        :param owns_context: Whether this transaction context owns *context* and should close it.
        """
        from ..mongodb import MongoProxyConnection
        self.__owns_context = owns_context is True
        self.__is_deev_context = isinstance(context, (MongoProxyConnection, MongoTransactionContext))
        mongo_database_name = getattr(context, 'mongo_database_name', None)
        assert mongo_database_name is not None, 'bad init'
        self.__context = context if self.__is_deev_context else MongoProxyConnection(context, mongo_database_name)  # type: ignore[arg-type]
        self.__transaction_id = uuid4().hex
        self.__transaction_depth = 0
        self.__savepoints: list[str] = []
        self.__transaction_name: str | None = None
        self.__cursor: DbCursor | None = None
        self.__database_name = context.mongo_database_name  # type: ignore[missing-attribute, union-attr]
        self.__delegate_mode = MongoTransactionContext._DELEGATE_TXN_CACHE.get(
            MongoTransactionContext.__server_key(self.mongo_client), None
        )
        if self.__delegate_mode is None:
            try:
                self.__delegate_mode = self._detect_delegated_mode(
                    self.__context.mongo_client   # type: ignore[attr-defined, union-attr]
                )
            except Exception:
                pass

    @staticmethod
    def __server_key(mongo_client: pymongo.MongoClient[Any]) -> tuple[str | None, int]:
        """Extract (hostname, port) from a pymongo.MongoClient as cache key."""
        return (mongo_client.HOST, mongo_client.PORT)

    @staticmethod
    def _detect_delegated_mode(mongo_client: pymongo.MongoClient[Any]) -> bool:
        """Return True when the server is known NOT to support transactions."""
        try:
            return 'replSetName' not in mongo_client.admin.command('ismaster')  # type: ignore[return-value]
        except Exception:
            # Can't determine — assume full transactional support (current safe default)
            return False

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

        For MongoDB: all TLC keywords return None (scrubbed) since MongoDB has
        no SQL transaction syntax. Side effects happen via mongo_session.
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
            if self.__transaction_depth == 1 and not self.__delegate_mode:
                self.mongo_session.start_transaction()
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
            if not self.__delegate_mode and self.__transaction_depth == -2:
                self.mongo_session.commit_transaction()
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
            if not self.__delegate_mode:
                self.mongo_session.abort_transaction()
            return None

        return sql

    @property
    def connection(self) -> DbConnection:
        if isinstance(self.__context, DbTransactionContext):
            return self.__context.connection
        else:
            return self.__context  # type: ignore[return-value]

    @property
    def mongo_client(self) -> pymongo.MongoClient[Any]:
        return self.connection.mongo_client  # type: ignore

    @property
    def mongo_database(self) -> pymongo.database.Database[Any]:
        return self.connection.mongo_client[self.__database_name]  # type: ignore

    @property
    def mongo_database_name(self) -> str:
        return self.__database_name

    @property
    def mongo_session(self) -> pymongo.client_session.ClientSession:
        return cast(MongoProxyCursor, self.__cursor).mongo_session  # type: ignore[attr-defined, valid-type]

    @property
    def transaction_name(self) -> str | None:
        return self.__transaction_name

    @property
    def savepoints(self) -> tuple[str, ...]:
        return tuple(self.__savepoints)

    def begin_transaction(self, name: str | None = None) -> Self:
        assert self.__context is not None, 'no context'
        self.__cursor = self.__context.cursor()
        if MongoTransactionContext.__ambient_transaction_id.get(None) is None:
            MongoTransactionContext.__ambient_transaction_id.set(name or self.__transaction_id)
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
        assert self.__cursor is not None, 'no cursor'
        return self.__cursor

    def execute(self, sql: str, parameters: DbParameters | None = None, raw: bool = False) -> DbCursor:
        if not raw:
            modified = self.__preprocess_sql(sql)
            if modified is None:
                from ..common.noop_cursor import NoopCursor
                return NoopCursor()
            sql = modified
        assert self.__cursor is not None, 'no cursor'
        self.__cursor.execute(
            sql,
            tuple(parameters) if parameters is not None else tuple())
        return self.__cursor

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


__all__ = ['MongoTransactionContext']
