# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from types import TracebackType
from typing import Any, Literal, Protocol, Self, runtime_checkable

from .async_db_cursor import AsyncDbCursor


@runtime_checkable
class AsyncDbConnection(Protocol):
    """Async DB-API 2.0 Connection proto."""

    async def cursor(self, *args: Any, **kwargs: Any) -> AsyncDbCursor:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> bool:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:  # type: ignore[override]
        """
        Return ``True`` if *subclass* implements all public attributes
        and methods defined on the ``AsyncDbConnection`` protocol.
        """
        required = {
            name
            for name in dir(AsyncDbConnection)
            if not name.startswith('_')
        }
        for name in required:
            if not hasattr(subclass, name):
                return False  # pragma: no cover
        return True


__all__ = ['AsyncDbConnection']
