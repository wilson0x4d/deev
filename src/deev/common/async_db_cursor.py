# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    Any,
    Sequence,
    Protocol,
    runtime_checkable
)

from .db_params import DbParams


@runtime_checkable
class AsyncDbCursor(Protocol):
    """Async DB-API 2.0 Cursor proto."""

    @property
    def description(self) -> Sequence[tuple[Any, Any, int | None, int | None, int | None, int | None, bool]] | None:
        ...

    @property
    def rowcount(self) -> int:
        ...

    async def execute(self, operation: str, params: DbParams | None = ...) -> None:
        ...

    async def executemany(self, operation: str, seq_params: Sequence[DbParams]) -> None:
        ...

    async def fetchone(self) -> tuple[Any, ...] | None:
        ...

    async def fetchmany(self, size: int = ...) -> list[tuple[Any, ...]]:
        ...

    async def fetchall(self) -> list[tuple[Any, ...]]:
        ...

    async def close(self) -> None:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:  # type: ignore[override]
        """
        Return ``True`` if *subclass* implements all public attributes
        and methods defined on the ``AsyncDbCursor`` protocol.
        """
        required = {
            name
            for name in dir(AsyncDbCursor)
            if not name.startswith('_')
        }
        for name in required:
            if not hasattr(subclass, name):
                return False  # pragma: no cover
        return True


__all__ = ['AsyncDbCursor']
