# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from types import TracebackType
from typing import (
    Any,
    Generator,
    Protocol,
    Self,
    runtime_checkable
)

from .db_connection import DbConnection
from .db_cursor import DbCursor
from .db_parameters import DbParameters

@runtime_checkable
class DbTransactionContext(Protocol):

    def __init__(self, connection: DbConnection, *, owns_context: bool | None = None) -> None:
        ...

    def __del__(self) -> None:
        ...

    def __enter__(self) -> Self:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> bool:
        ...

    @property
    def connection(self) -> DbConnection:
        ...

    @property
    def transaction_name(self) -> str | None:
        ...

    @property
    def savepoints(self) -> tuple[str, ...]:
        ...

    def cursor(self) -> DbCursor:
        ...

    def begin_transaction(self, name: str | None = None) -> Self:
        ...

    def commit(self) -> None:
        ...

    def execute(self, sql: str, parameters: DbParameters | None = ...) -> DbCursor:
        ...

    def execute_script(self, sql: str, raw: bool = ...) -> None:
        ...

    def execute_nonquery(self, sql: str, parameters: DbParameters | None = ...) -> None:
        ...

    def execute_reader(self, sql: str, parameters: DbParameters | None = ...) -> Generator[tuple[Any, ...], None, None]:
        ...

    def execute_scalar(self, sql: str, parameters: DbParameters | None = ...) -> Any:
        ...

    def rollback(self, name: str | None = None) -> None:
        ...

    def rollback_savepoint(self, name: str | None = None) -> None:
        ...

    def close(self) -> None:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:  # type: ignore[override]
        """
        Return ``True`` if *subclass* implements all public attributes
        and methods defined on the ``DbTransactionContext`` protocol.
        """
        required = {
            name
            for name in dir(DbTransactionContext)
            if not name.startswith('_')
        }
        for name in required:
            if not hasattr(subclass, name):
                return False  # pragma: no cover
        return True

__all__ = ['DbTransactionContext']
