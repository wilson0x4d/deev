# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from types import TracebackType
from typing import Any, Literal, Optional, Protocol, Self, runtime_checkable

from .DbCursor import DbCursor


@runtime_checkable
class DbConnection(Protocol):
    """DB-API 2.0 Connection proto."""

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...

    def __enter__(self) -> Self:
        ...

    def __exit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType], /) -> Literal[False]:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:  # type: ignore[override]
        """
        Return ``True`` if *subclass* implements all public attributes
        and methods defined on the ``DbConnection`` protocol.
        """
        required = {
            name
            for name in dir(DbConnection)
            if not name.startswith('_')
        }
        for name in required:
            if not hasattr(subclass, name):
                return False  # pragma: no cover
        return True


__all__ = ['DbConnection']
