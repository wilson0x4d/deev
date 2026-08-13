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
        ...

    async def rollback(self) -> None:
        ...

    async def create(self, entity: TEntity) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided keyword arguments.

        :param kwargs: A dictionary containing the column names and their corresponding values for the new record.
        :type kwargs: dict[str, Any]
        :return: The newly created record's ID if successful, otherwise None.
        :rtype: Any
        """
        ...

    async def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by `kwargs`.

        :param kwargs: The primary key.
        :type kwargs: dict[str, Any]
        :return: A dictionary containing the column names and their corresponding values for the specified record, or None if no such record exists.
        :rtype: dict[str, Any] | None
        """
        ...

    async def update(self, entity: TEntity) -> None:
        ...

    async def delete(self, **kwargs: Any) -> None:
        ...

    async def exists(self, **kwargs: Any) -> bool:
        ...

    async def upsert(self, entity: TEntity) -> dict[str, Any]:
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
