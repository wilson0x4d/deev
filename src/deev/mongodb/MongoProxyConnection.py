# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pymongo
from types import TracebackType
from typing import Any, Literal, Optional, Self

from ..common.DbConnection import DbConnection
from ..common.DbCursor import DbCursor
from .MongoProxyCursor import MongoProxyCursor


class MongoProxyConnection(DbConnection):
    """
    DB-API 2.0 compliant connection interface for MongoDB.
    """
    __client: pymongo.MongoClient[Any]
    __database_name: str

    def __init__(self, provider_connection: pymongo.MongoClient[Any], database_name: str) -> None:
        self.__client = provider_connection
        self.__database_name = database_name

    @property
    def mongo_client(self) -> pymongo.MongoClient[Any]:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.__client

    @property
    def mongo_database(self) -> pymongo.database.Database[Any]:
        # NOTE: this is a non-conformant property that we require for migration scripts (QOL), and must be retained.
        return self.mongo_client[self.mongo_database_name]

    @property
    def mongo_database_name(self) -> str:
        # NOTE: this is a non-conformant property that we require for internal functionality, and it must be retained.
        return self.__database_name.split('?')[0]

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        return MongoProxyCursor(self.mongo_client.start_session(), self.mongo_database_name)

    def commit(self) -> None:
        # MongoDB transactions are session-based; for non-sessioned connections this is a no-op.
        # Use MongoTransactionContext for transactional operations.
        pass

    def rollback(self) -> None:
        # MongoDB transactions are session-based; for non-sessioned connections this is a no-op.
        # Use MongoTransactionContext for transactional operations.
        pass

    def close(self) -> None:
        self.mongo_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType], /) -> bool:
        self.mongo_client.__exit__(exc_type, exc, tb)  # type: ignore[arg-type]
        return exc is not None


__all__ = ['MongoProxyConnection']
