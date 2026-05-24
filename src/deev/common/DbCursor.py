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

from .DbParams import DbParams


@runtime_checkable
class DbCursor(Protocol):
    """DB-API 2.0 Cursor proto."""

    @property
    def description(self) -> Optional[Sequence[tuple[Any, ...]]]:
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


__all__ = ['DbCursor']
