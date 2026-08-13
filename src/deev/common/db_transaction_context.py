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
from .db_params import DbParams

@runtime_checkable
class DbTransactionContext(Protocol):

    def __init__(self, connection: DbConnection) -> None:
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

    def cursor(self) -> DbCursor:
        ...

    def commit(self) -> None:
        ...

    def execute(self, sql: str, params: DbParams | None = ...) -> DbCursor:
        ...

    def execute_script(self, sql: str) -> None:
        ...

    def execute_nonquery(self, sql: str, params: DbParams | None = ...) -> None:
        ...

    def execute_reader(self, sql: str, params: DbParams | None = ...) -> Generator[tuple[Any, ...], None, None]:
        ...

    def execute_scalar(self, sql: str, params: DbParams | None = ...) -> Any:
        ...

    def rollback(self) -> None:
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
