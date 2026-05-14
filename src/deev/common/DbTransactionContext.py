# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from types import TracebackType
from typing import (
    Any,
    Generator,
    Optional,
    Protocol,
    runtime_checkable
)

from .DbConnection import DbConnection
from .DbCursor import DbCursor
from .DbParams import DbParams


@runtime_checkable
class DbTransactionContext(Protocol):

    def __init__(self, connection: DbConnection) -> None:
        ...

    def __del__(self) -> None:
        ...

    def __enter__(self) -> DbTransactionContext:
        ...

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None
    ) -> bool:
        ...

    @property
    def connection(self) -> DbConnection:
        ...

    def cursor(self) -> DbCursor:
        ...

    def commit(self) -> None:
        ...

    def execute(self, sql: str, params: Optional[DbParams] = ...) -> DbCursor:
        ...

    def execute_script(self, sql: str) -> None:
        ...

    def execute_nonquery(self, sql: str, params: Optional[DbParams] = ...) -> None:
        ...

    def execute_reader(self, sql: str, params: Optional[DbParams] = ...) -> Generator[tuple[Any, ...], None, None]:
        ...

    def execute_scalar(self, sql: str, params: Optional[DbParams] = ...) -> Any:
        ...

    def rollback(self) -> None:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:   # type: ignore[override]
        # if db api providers can't be bothered to follow the
        # spec anyone else can't be bothered to enforce it.
        required = {
            name
            for name in dir(cls)
            if not name.startswith('_')
        }
        for name in required:
            if name not in subclass.__dict__:
                return False  # pragma: no cover
        return True


__all__ = ['DbTransactionContext']
