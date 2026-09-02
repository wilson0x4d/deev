# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

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
    runtime_checkable,
)

import hanaro

from .db_connection import DbConnection
from .db_cursor import DbCursor
from .db_table_adapter import DbTableAdapter
from .db_transaction_context import DbTransactionContext
from .connection_string import ConnectionString

TEntity = TypeVar('TEntity')


class DbAdapter(DbConnection, ABC):
    """
    Abstract base for database context adapters.

    Subclasses need only define table adapter properties.
    ``__init_subclass__`` auto-discovers ``DbTableAdapter`` properties
    and ``get_table_adapter`` lazily creates and caches adapters based
    on the connection string provider.

    The ``get_table_adapter`` method delegates to ``utils.create_table_adapter``
    and accepts the same keyword arguments (``create_table``, ``table_name``,
    ``**kwargs``). Callers can pass provider-specific options such as
    ``sync_replicas=True`` for ClickHouse adapters.

    Usage
    -----

    .. code-block:: python

        class AssetsDbContext(DbAdapter):
            def __init__(self, connection_string: ConnectionString | str):
                super().__init__(connection_string)

            @property
            def documents(self) -> MongoTableAdapter[Document]:
                return self.get_table_adapter(Document)
    """

    __adapter_map = dict[str, tuple[type, str]]()
    __adapter_cache: dict[tuple[str, bool, str | None, frozenset[tuple[str, Any]]], object]
    __connection: DbConnection | None
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
                self.__connection.close()
        except Exception:
            pass

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
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
    def connection(self) -> DbConnection:
        assert self.__connection is not None, 'not connected'
        return self.__connection

    def begin_transaction(self, **kwargs: Any) -> DbTransactionContext:
        assert self.__connection is not None, 'not connected'
        from ..utils import begin_transaction
        return begin_transaction(self.__connection, **kwargs)

    def close(self) -> None:
        if self.__connection is not None:
            self.__connection.close()
            self.__connection = None

    def commit(self) -> None:
        assert self.__connection is not None, 'not connected'
        self.__connection.commit()

    def connect(self) -> None:
        """
        Establish a connection and initialize the adapter cache.
        Subclasses may override to add custom logic *after* calling ``super().connect()``.
        """
        from ..utils import connect as _connect
        for _entity_type, cache_attr in self.__adapter_map.values():
            if cache_attr not in self.__dict__:
                object.__setattr__(self, cache_attr, None)
        if self.__connection is None:
            object.__setattr__(self, '_DbAdapter__connection', _connect(self.__connection_string))

    def cursor(self, *args: Any, **kwargs: Any) -> DbCursor:
        assert self.__connection is not None, 'not connected'
        return self.__connection.cursor(*args, **kwargs)  # type: ignore[return-value]

    def get_table_adapter(
        self,
        entity_type: type[TEntity],
        *,
        create_table: bool = False,
        table_name: str | None = None,
        **kwargs: Any
    ) -> DbTableAdapter[TEntity]:
        key = entity_type.__name__
        registered = self.__adapter_map.get(key)
        if registered is None:
            raise KeyError(f"No table adapter registered for entity type '{key}'.")

        _entity_type, cache_attr = registered

        assert self.__connection is not None, 'not connected'

        cache_key = (cache_attr, create_table, table_name, frozenset(kwargs.items()))
        adapter = self.__adapter_cache.get(cache_key)
        if adapter is None:
            from ..utils import db_table_adapter_factory
            adapter = db_table_adapter_factory(
                entity_type,
                self.__connection,
                create_table=create_table,
                table_name=table_name,
                **kwargs
            )  # type: ignore[arg-type]
            self.__adapter_cache[cache_key] = adapter  # type: ignore[literal-required]
        return cast(DbTableAdapter[TEntity], adapter)

    def rollback(self) -> None:
        assert self.__connection is not None, 'not connected'
        self.__connection.rollback()


__all__ = ['DbAdapter']
