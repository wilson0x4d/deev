# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    Any,
    Sequence,
    TypeAlias,
)

from .db_cursor import DbCursor
from .description_field import DescriptionField


DbCursorDescription: TypeAlias = Sequence[DescriptionField] | None


class NoopCursor(DbCursor):
    """
    A cursor stub returned when ``__preprocess_sql`` returns ``None`` (scrubbed).

    Used when ``execute`` must return a valid ``DbCursor`` but the SQL was
    intentionally suppressed (e.g., a nested COMMIT at depth > 1 on a DBMS
    that does not support nested transactions).

    Instantiated on-demand per call — do not cache or share.
    """

    __description: DbCursorDescription
    __rowcount: int

    def __init__(self) -> None:
        self.__description = None
        self.__rowcount = 0

    @property
    def description(self) -> DbCursorDescription:
        return self.__description

    @property
    def rowcount(self) -> int:
        return self.__rowcount

    def execute(self, operation: str, parameters: Any | None = None) -> None:
        pass

    def executemany(self, operation: str, seq_of_parameters: Sequence[Any]) -> None:
        pass

    def fetchone(self) -> tuple[Any, ...] | None:
        return None

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        return []

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def close(self) -> None:
        pass


__all__ = ['NoopCursor']
