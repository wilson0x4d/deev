# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import logging
import sys
from abc import ABC
from types import TracebackType
from typing import (
    Any,
    Literal,
    Self,
    TypeVar,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

import hanaro

from .async_db_connection import AsyncDbConnection
from .async_db_cursor import AsyncDbCursor
from .async_db_table_adapter import AsyncDbTableAdapter
from .async_db_transaction_context import AsyncDbTransactionContext
from .connection_string import ConnectionString

TEntity = TypeVar('TEntity')


class AsyncDbAdapter(AsyncDbConnection, ABC):
    """
    Abstract base for async database context adapters.

    Subclasses need only define table adapter properties.
    ``__init_subclass__`` auto-discovers ``AsyncDbTableAdapter`` properties
    and ``get_table_adapter`` lazily creates and caches adapters based
    on the connection string provider.

    The ``get_table_adapter`` method delegates to ``utils.create_table_adapter_async``
    and accepts the same keyword arguments (``create_table``, ``table_name``,
    ``**kwargs``). Callers can pass provider-specific options such as
    ``sync_replicas=True`` for ClickHouse adapters.

    Usage
    -----

    .. code-block:: python

        class AssetsDbContext(AsyncDbAdapter):
            def __init__(self, connection_string: ConnectionString | str):
                super().__init__(connection_string)

            @property
            def documents(self) -> AsyncMongoTableAdapter[Document]:
                return self.get_table_adapter(Document)
    """

    __adapter_map = dict[str, tuple[type, str]]()
    __adapter_cache: dict[tuple[str, bool, str | None, frozenset[tuple[str, Any]]], object]
    __connection: AsyncDbConnection | None
    __connection_string: ConnectionString | str
    __logger: logging.Logger

    def __init__(self, connection_string: ConnectionString | str) -> None:
        self.__connection = None
        self.__logger = hanaro.get_queued_logger()
        self.__connection_string = connection_string
        self.__adapter_cache = {}

    def __del__(self) -> None:
        try:
            if self.__connection is not None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(self.__connection.close())
                else:
                    asyncio.run(self.__connection.close())
        except Exception:
            pass

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> Literal[False]:
        return False

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        mod = sys.modules[cls.__module__]
        mod_globals = vars(mod)

        for name, prop in cls.__dict__.items():
            if not isinstance(prop, property):
                continue
            fget = prop.fget
            if fget is None:
                continue
            try:
                hints = get_type_hints(fget, globalns=mod_globals)
            except Exception:
                continue  # property type cannot be resolved

            for hint in hints.values():
                type_args = get_args(hint)
                if len(type_args) == 1:
                    entity_type = type_args[0]
                    cache_attr = f'_adapter__{name}'
                    cls.__adapter_map[entity_type.__name__] = (entity_type, cache_attr)
                    break

    @property
    def connection(self) -> AsyncDbConnection:
        assert self.__connection is not None, 'not connected'
        return self.__connection

    async def begin_transaction(self, **kwargs: Any) -> AsyncDbTransactionContext:
        assert self.__connection is not None, 'not connected'
        from ..utils import begin_transaction_async
        return await begin_transaction_async(self.__connection, **kwargs)

    async def close(self) -> None:
        if self.__connection is not None:
            await self.__connection.close()
            self.__connection = None

    async def commit(self) -> None:
        assert self.__connection is not None, 'not connected'
        await self.__connection.commit()

    async def connect(self) -> None:
        """
        Establish a connection and initialize the adapter cache.
        Subclasses may override to add custom logic *after* calling ``super().connect()``.
        """
        from ..utils import connect_async
        for _entity_type, cache_attr in self.__adapter_map.values():
            if cache_attr not in self.__dict__:
                object.__setattr__(self, cache_attr, None)
        if self.__connection is None:
            self.__connection = await connect_async(self.__connection_string)

    async def cursor(self, *args: Any, **kwargs: Any) -> AsyncDbCursor:
        assert self.__connection is not None, 'not connected'
        return await self.__connection.cursor(*args, **kwargs)  # type: ignore[return-value]

    def get_table_adapter(
        self,
        entity_type: type[TEntity],
        *,
        create_table: bool = False,
        table_name: str | None = None,
        **kwargs: Any
    ) -> AsyncDbTableAdapter[TEntity]:
        key = entity_type.__name__
        registered = self.__adapter_map.get(key)
        if registered is None:
            raise KeyError(f"No table adapter registered for entity type '{key}'.")

        _entity_type, cache_attr = registered

        assert self.__connection is not None, 'not connected'

        cache_key = (cache_attr, create_table, table_name, frozenset(kwargs.items()))
        adapter = self.__adapter_cache.get(cache_key)
        if adapter is None:
            from ..utils import create_table_adapter_async
            adapter = create_table_adapter_async(
                entity_type,
                self.__connection,
                create_table=create_table,
                table_name=table_name,
                **kwargs
            )  # type: ignore[return-value]
            self.__adapter_cache[cache_key] = adapter  # type: ignore[literal-required]
        return cast(AsyncDbTableAdapter[TEntity], adapter)

    async def rollback(self) -> None:
        assert self.__connection is not None, 'not connected'
        await self.__connection.rollback()


__all__ = ['AsyncDbAdapter']
