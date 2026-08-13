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
from .db_params import DbParams


@runtime_checkable
class AsyncDbTransactionContext(Protocol):

    def __init__(self, connection: AsyncDbConnection) -> None:
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

    async def cursor(self) -> AsyncDbCursor:
        ...

    async def commit(self) -> None:
        ...

    async def execute(self, sql: str, params: DbParams | None = ...) -> AsyncDbCursor:
        ...

    async def execute_script(self, sql: str) -> None:
        ...

    async def execute_nonquery(self, sql: str, params: DbParams | None = ...) -> None:
        ...

    async def execute_reader(self, sql: str, params: DbParams | None = ...) -> AsyncGenerator[tuple[Any, ...], None]:
        ...

    async def execute_scalar(self, sql: str, params: DbParams | None = ...) -> Any:
        ...

    async def rollback(self) -> None:
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
