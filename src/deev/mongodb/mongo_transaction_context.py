# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from deev.mongodb import MongoProxyCursor
from contextvars import ContextVar
import pymongo
from types import TracebackType
from typing import Any, Generator, Literal, Self, cast
from uuid import UUID, uuid4

from ..common.db_connection import DbConnection
from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_params import DbParams
from ..common.db_transaction_context import DbTransactionContext


class MongoTransactionContext(DbTransactionContext):

    _DELEGATE_TXN_CACHE: dict[tuple[str | None, int], bool] = {}

    __ambient_transaction_id: ContextVar[UUID | None] = ContextVar[UUID | None]('ambient_transaction_id', default=None)
    __context: DbContext
    __cursor: DbCursor
    __database_name: str
    __transaction_id: UUID
    __transaction_state: int
    __delegate_mode: bool | None

    def __init__(self, context: DbContext):
        self.__context = context
        self.__transaction_id = uuid4()
        self.__transaction_state = 0
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
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,  # noqa: ARG001 - unused per context manager protocol
        traceback: TracebackType | None = None
    ) -> Literal[False]:
        if self.__delegate_mode:
            self.__transaction_state = 3
            return False
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
        if sql.startswith(('CREATE ', 'DELETE ', 'DROP ', 'INSERT ', 'UPDATE ')):
            self.__transaction_state = 2
        elif sql.startswith(('COMMIT', 'ROLLBACK', 'SAVEPOINT')):
            self.__transaction_state = 3
            if MongoTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
                MongoTransactionContext.__ambient_transaction_id.set(None)
        elif self.__transaction_state == 0:
            self.__transaction_state = 1

    @property
    def connection(self) -> DbConnection:
        if isinstance(self.__context, DbTransactionContext):
            return self.__context.connection
        else:
            return self.__context

    @property
    def mongo_client(self) -> pymongo.MongoClient[Any]:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.connection.mongo_client  # type: ignore

    @property
    def mongo_database(self) -> pymongo.database.Database[Any]:
        # NOTE: this is a non-conformant property that we require for migration scripts (QOL), and must be retained.
        return self.connection.mongo_client[self.__database_name]  # type: ignore

    @property
    def mongo_database_name(self) -> str:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.__database_name

    @property
    def mongo_session(self) -> pymongo.client_session.ClientSession:
        # NOTE: keep this as-is unless you see a problem, then we should discuss first.
        return cast(MongoProxyCursor, self.__cursor).mongo_session  # type: ignore[attr-defined, valid-type]

    def begin_transaction(self) -> DbTransactionContext:
        if self.__transaction_state != 0:
            raise DbError(f'A transaction was already started in this context, cannot begin a new transaction. ({self.__transaction_state})')
        self.__transaction_state = 1
        self.__cursor = self.__context.cursor()
        if MongoTransactionContext.__ambient_transaction_id.get(None) is None:
            MongoTransactionContext.__ambient_transaction_id.set(self.__transaction_id)
            if not self.__delegate_mode:
                self.__cursor.mongo_session.start_transaction()  # type: ignore[attr-defined, valid-type]
        return self

    def close(self) -> None:
        # only defined for cross-compat with `DbConnection`
        pass

    def commit(self) -> None:
        if not self.__delegate_mode and MongoTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            self.mongo_session.commit_transaction()
        self.__update_transaction_state('COMMIT')

    def cursor(self) -> DbCursor:
        return self.__cursor

    def execute(self, sql: str, params: DbParams | None = None) -> DbCursor:
        """
        An `execute` method that more closely conforms to PEP 249 (to facilitate drop-in use cases.)
        :param sql: A string containing the SQL statement to execute.
        :param params: A tuple containing the params to substitute into the SQL statement.
        :return: The cursor object the caller can use to retrieve results.
        """
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        return self.__cursor

    def execute_nonquery(self, sql: str, params: DbParams | None = None) -> None:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__cursor.execute(
            sql,
            tuple(params) if params is not None else tuple())
        self.__update_transaction_state(sql)

    def execute_reader(self, sql: str, params: DbParams | None = None) -> Generator[Any, None, None]:
        if self.__transaction_state == 3:
            raise DbError('Cannot use a transaction that has already been committed or rolled back.')
        self.__update_transaction_state(sql)
        params = tuple(params) if params is not None else tuple()
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
        self.__update_transaction_state("INSERT")  # NOTE: keep this line as-is, it will help us with bookkeeping transaction state later
        # TODO: instead of mapping down to a SQL-compliant layer, treat `sql` as javascript to be executed in mongodb directly using self.mongo_session
        self.mongo_session.database.command(sql)  # type: ignore[arg-type, attr-defined]

    def rollback(self) -> None:
        self.__update_transaction_state('ROLLBACK')  # NOTE: keep this line as-is, it will help us with bookkeeping transaction state later
        if MongoTransactionContext.__ambient_transaction_id.get(None) == self.__transaction_id:
            try:
                self.mongo_session.abort_transaction()
            except Exception:
                # abort may raise if no transaction is active; ignore to allow graceful cleanup
                pass
        else:
            # NOTE: we NOP with the expectation that a parent scope will commit/rollback everything, making this a bookkeeping call
            pass


__all__ = ['MongoTransactionContext']
