# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    Any,
    Optional,
    Sequence,
    Protocol,
    runtime_checkable
)

from .db_params import DbParams


@runtime_checkable
class DbCursor(Protocol):
    """DB-API 2.0 Cursor proto."""

    @property
    def description(self) -> Optional[Sequence[tuple[Any, Any, Optional[int], Optional[int], Optional[int], Optional[int], bool]]]:
        ...

    @property
    def rowcount(self) -> int:
        ...

    def execute(self, operation: str, params: Optional[DbParams] = ...) -> None:
        ...

    def executemany(self, operation: str, seq_of_params: Sequence[DbParams]) -> None:
        ...

    def fetchone(self) -> tuple[Any, ...] | None:
        ...

    def fetchmany(self, size: int = ...) -> list[tuple[Any, ...]]:
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        ...

    def close(self) -> None:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool | None:  # type: ignore[override]
        """
        Return ``True`` if *subclass* implements all public attributes
        and methods defined on the ``DbCursor`` protocol.
        """
        required = {
            name
            for name in dir(DbCursor)
            if not name.startswith('_')
        }
        for name in required:
            if not hasattr(subclass, name):
                return False  # pragma: no cover
        return True


__all__ = ['DbCursor']
