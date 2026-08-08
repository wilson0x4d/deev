# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    Any,
    Generator,
    Optional,
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
        ...

    def rollback(self) -> None:
        ...

    def create(self, entity: TEntity) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided keyword arguments.

        :param kwargs: A dictionary containing the column names and their corresponding values for the new record.
        :type kwargs: dict[str, Any]
        :return: The newly created record's ID if successful, otherwise None.
        :rtype: Any
        """
        ...

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by `kwargs`.

        :param kwargs: The primary key.
        :type kwargs: dict[str, Any]
        :return: A dictionary containing the column names and their corresponding values for the specified record, or None if no such record exists.
        :rtype: dict[str, Any] | None
        """
        ...

    def update(self, entity: TEntity) -> None:
        ...

    def delete(self, **kwargs: Any) -> None:
        ...

    def exists(self, **kwargs: Any) -> bool:
        ...

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        ...

    def query(
        self,
        where: Optional[str] = ...,
        params: Optional[DbParams] = ...,
        orderby: Optional[str] = ...,
        limit: Optional[int] = ...
    ) -> Generator[TEntity, None, None]:
        ...


__all__ = ['DbTableAdapter']
