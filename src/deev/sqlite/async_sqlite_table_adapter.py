# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, AsyncGenerator, TypeVar, cast, get_args, get_origin

from ..common.async_db_table_adapter import AsyncDbTableAdapter
from ..common.db_context import AsyncDbContext
from ..common.db_params import DbParams
from ..entities import get_entity_spec
from .async_sqlite_proxy_connection import AsyncSqliteProxyConnection
from .async_sqlite_transaction_context import AsyncSqliteTransactionContext
from .sqlite_proxy_connection import SqliteProxyConnection
from .sqlite_table_adapter import SqliteTableAdapter
from .sqlite_type_mapper import SqliteTypeMapper

TEntity = TypeVar('TEntity')


class AsyncSqliteTableAdapter(AsyncDbTableAdapter[TEntity]):
    """
    Async shim that delegates to ``SqliteTableAdapter``.

    Since sqlite3 has no native async API, all calls are forwarded to the
    synchronous table adapter using ``asyncio.to_thread``.
    """

    __sync_adapter: SqliteTableAdapter[TEntity]
    __context: AsyncDbContext
    __create_table: bool
    __table_name: str | None

    def __init__(
        self,
        context: AsyncDbContext,
        *,
        create_table: bool = False,
        table_name: str | None = None
    ) -> None:
        """Initialize the async SQLite table adapter (delegates to sync via ``asyncio.to_thread``)."""
        self.__context = context if isinstance(context, (AsyncSqliteProxyConnection, AsyncSqliteTransactionContext)) else AsyncSqliteProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__table_name = table_name
        self.__is_initialized = False

    async def __deferred_init(self) -> None:
        if not self.__is_initialized:
            self.__is_initialized = True
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
            self.__dbtype_mapper = SqliteTypeMapper(self.__entity_spec)

            self.__sync_adapter = SqliteTableAdapter[entity_type](  # type: ignore[valid-type]
                self.sqlite_connection,
                create_table=self.__create_table,
                table_name=self.__table_name,
            )
            if self.__create_table is True:
                await self.create_table()

    def __get_typearg(self, obj: object) -> type:
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is AsyncSqliteTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. AsyncSqliteTableAdapter[MyEntity]().'
        )

    @property
    def primary_key(self) -> tuple[str, ...]:
        sync_adapter = getattr(self, '_AsyncSqliteTableAdapter__sync_adapter', None)
        if sync_adapter is None:
            raise RuntimeError('AsyncSqliteTableAdapter.primary_key requires deferred init; call create_table() or another method first.')
        return sync_adapter.primary_key

    @property
    def sqlite_connection(self) -> SqliteProxyConnection:
        if isinstance(self.__context, AsyncSqliteProxyConnection):
            return self.__context.sqlite_connection
        elif isinstance(self.__context, AsyncSqliteTransactionContext):
            return cast(AsyncSqliteProxyConnection, self.__context.connection).sqlite_connection
        raise RuntimeError(f'unsupported context type: {self.__context}')

    async def create_table(self) -> None:
        await self.__deferred_init()
        self.__sync_adapter.create_table()
        self.__create_table = False

    async def create(self, entity: TEntity | None = None, **kwargs: Any) -> dict[str, Any]:
        await self.__deferred_init()
        return self.__sync_adapter.create(entity, **kwargs)

    async def read(self, **kwargs: Any) -> TEntity | None:
        await self.__deferred_init()
        return self.__sync_adapter.read(**kwargs)

    async def update(self, entity: TEntity) -> None:
        await self.__deferred_init()
        self.__sync_adapter.update(entity)

    async def delete(self, **kwargs: Any) -> None:
        await self.__deferred_init()
        self.__sync_adapter.delete(**kwargs)

    async def exists(self, **kwargs: Any) -> bool:
        await self.__deferred_init()
        return self.__sync_adapter.exists(**kwargs)

    async def upsert(self, entity: TEntity) -> dict[str, Any]:
        await self.__deferred_init()
        return self.__sync_adapter.upsert(entity)

    async def query(  # type: ignore[override]
        self,
        where: str | None = None,
        params: DbParams | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> AsyncGenerator[TEntity, None]:
        await self.__deferred_init()
        sync_gen = self.__sync_adapter.query(where, params, orderby, limit)
        for e in sync_gen:
            yield e

    async def commit(self) -> None:
        await self.__deferred_init()
        self.__sync_adapter.commit()

    async def rollback(self) -> None:
        await self.__deferred_init()
        self.__sync_adapter.rollback()


__all__ = ['AsyncSqliteTableAdapter']
