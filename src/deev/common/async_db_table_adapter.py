# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    Any,
    AsyncGenerator,
    Protocol,
    TypeVar,
    runtime_checkable
)

from .db_params import DbParams

TEntity = TypeVar('TEntity')


@runtime_checkable
class AsyncDbTableAdapter(Protocol[TEntity]):

    async def create_table(self) -> None:
        """Utility method for creating the target table."""
        ...

    async def commit(self) -> None:
        """Commit the current transaction."""
        ...

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    async def create(self, entity: TEntity) -> dict[str, Any]:
        """
        Creates a new record in the specified table.

        :param entity: An entity instance of type ``TEntity``.
        :return: The primary key values of the created record.
        """
        ...

    async def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by ``kwargs``.

        :param kwargs: The primary key field names and values.
        :return: The hydrated entity or ``None`` if no such record exists.
        """
        ...

    async def update(self, entity: TEntity) -> None:
        ...

    async def delete(self, **kwargs: Any) -> None:
        ...

    async def exists(self, **kwargs: Any) -> bool:
        ...

    async def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Insert or update a record.

        :param entity: Entity instance.
        :return: The primary key values of the record.
        """
        ...

    async def query(
        self,
        where: str | None = ...,
        params: DbParams | None = ...,
        orderby: str | None = ...,
        limit: int | None = ...
    ) -> AsyncGenerator[TEntity, None]:
        ...


__all__ = ['AsyncDbTableAdapter']
