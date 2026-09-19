# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from types import TracebackType
from typing import (
    Any,
    AsyncGenerator,
    Protocol,
    Self,
    runtime_checkable
)

from .async_db_connection import AsyncDbConnection
from .async_db_cursor import AsyncDbCursor
from .db_parameters import DbParameters


@runtime_checkable
class AsyncDbTransactionContext(Protocol):

    def __init__(self, connection: AsyncDbConnection, *, owns_context: bool | None = None) -> None:
        ...

    def __del__(self) -> None:
        ...

    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None
    ) -> bool:
        ...

    @property
    def connection(self) -> AsyncDbConnection:
        ...

    @property
    def transaction_name(self) -> str | None:
        ...

    @property
    def savepoints(self) -> tuple[str, ...]:
        ...

    async def cursor(self) -> AsyncDbCursor:
        ...

    async def begin_transaction(self, name: str | None = None) -> Self:
        ...

    async def commit(self) -> None:
        ...

    async def create_savepoint(self, name: str | None = None) -> Self:
        ...

    async def execute(self, sql: str, parameters: DbParameters | None = ..., raw: bool = ...) -> AsyncDbCursor:
        ...

    async def execute_script(self, sql: str) -> None:
        ...

    async def execute_nonquery(self, sql: str, parameters: DbParameters | None = ...) -> None:
        ...

    async def execute_reader(self, sql: str, parameters: DbParameters | None = ...) -> AsyncGenerator[tuple[Any, ...], None]:
        ...

    async def execute_scalar(self, sql: str, parameters: DbParameters | None = ...) -> Any:
        ...

    async def rollback(self, name: str | None = None) -> None:
        ...

    async def rollback_savepoint(self, name: str | None = None) -> None:
        ...

    async def close(self) -> None:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:  # type: ignore[override]
        """
        Return ``True`` if *subclass* implements all public attributes
        and methods defined on the ``AsyncDbTransactionContext`` protocol.
        """
        required = {
            name
            for name in dir(AsyncDbTransactionContext)
            if not name.startswith('_')
        }
        for name in required:
            if not hasattr(subclass, name):
                return False  # pragma: no cover
        return True


__all__ = ['AsyncDbTransactionContext']
