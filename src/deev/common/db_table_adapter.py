# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    Any,
    Generator,
    Protocol,
    TypeVar,
    runtime_checkable
)

from .db_params import DbParams


TEntity = TypeVar('TEntity')


@runtime_checkable
class DbTableAdapter(Protocol[TEntity]):

    def create_table(self) -> None:
        """Utility method for creating the target table."""
        ...

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    def create(self, entity: TEntity) -> dict[str, Any]:
        """
        Creates a new record in the specified table.

        :param entity: An entity instance of type ``TEntity``.
        :return: The primary key values of the created record.
        """
        ...

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by ``kwargs``.

        :param kwargs: The primary key field names and values.
        :return: The hydrated entity or ``None`` if no such record exists.
        """
        ...

    def update(self, entity: TEntity) -> None:
        ...

    def delete(self, **kwargs: Any) -> None:
        ...

    def exists(self, **kwargs: Any) -> bool:
        ...

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Insert or update a record.

        :param entity: Entity instance.
        :return: The primary key values of the record.
        """
        ...

    def query(
        self,
        where: str | None = ...,
        params: DbParams | None = ...,
        orderby: str | None = ...,
        limit: int | None = ...
    ) -> Generator[TEntity, None, None]:
        ...


__all__ = ['DbTableAdapter']
