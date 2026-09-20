# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, AsyncGenerator, TypeVar, cast, get_args, get_origin

from ..common.async_db_table_adapter import AsyncDbTableAdapter
from ..common.db_context import AsyncDbContext
from ..common.db_parameters import DbParameters
from ..entities import get_entity_spec
from .async_mssql_proxy_connection import AsyncMSSQLProxyConnection
from .async_mssql_transaction_context import AsyncMSSQLTransactionContext
from .mssql_proxy_connection import MSSQLProxyConnection
from .mssql_table_adapter import MSSQLTableAdapter
from .mssql_type_mapper import MSSQLTypeMapper

TEntity = TypeVar('TEntity')


class AsyncMSSQLTableAdapter(AsyncDbTableAdapter[TEntity]):
    """
    Async shim that delegates to ``MSSQLTableAdapter``.

    Since mssql_python has no native async API, all calls are forwarded to the
    synchronous table adapter using ``asyncio.to_thread``.
    """

    __sync_adapter: MSSQLTableAdapter[TEntity]
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
        self.__context = context if isinstance(context, (AsyncMSSQLProxyConnection, AsyncMSSQLTransactionContext)) else AsyncMSSQLProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__table_name = table_name
        self.__is_initialized = False

    async def __deferred_init(self) -> None:
        if not self.__is_initialized:
            self.__sync_deferred_init()
            self.__is_initialized = True
            if self.__create_table is True:
                await self.create_table()

    def __sync_deferred_init(self) -> None:
        entity_type = self.__get_typearg(self)
        self.__entity_spec = get_entity_spec(entity_type)
        self.__column_names = ', '.join([f'[{k}]' for k in self.__entity_spec.fields.keys()])
        self.__dbtype_mapper = MSSQLTypeMapper(self.__entity_spec)

        self.__sync_adapter = MSSQLTableAdapter[entity_type](  # type: ignore[valid-type]
            self.mssql_connection,
            create_table=self.__create_table,
            table_name=self.__table_name,
        )

    @property
    def primary_key(self) -> tuple[str, ...]:
        if not hasattr(self, '_AsyncMSSQLTableAdapter__sync_adapter'):
            self.__sync_deferred_init()
        return self.__sync_adapter.primary_key

    def __get_typearg(self, obj: object) -> type:
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is AsyncMSSQLTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. AsyncMSSQLTableAdapter[MyEntity]().'
        )

    @property
    def mssql_connection(self) -> MSSQLProxyConnection:
        if isinstance(self.__context, AsyncMSSQLProxyConnection):
            return self.__context.mssql_connection
        elif isinstance(self.__context, AsyncMSSQLTransactionContext):
            return cast(AsyncMSSQLProxyConnection, self.__context.connection).mssql_connection
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
        parameters: DbParameters | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> AsyncGenerator[TEntity, None]:
        await self.__deferred_init()
        sync_gen = self.__sync_adapter.query(where, parameters, orderby, limit)
        for e in sync_gen:
            yield e

    async def commit(self) -> None:
        await self.__deferred_init()
        self.__sync_adapter.commit()

    async def rollback(self) -> None:
        await self.__deferred_init()
        self.__sync_adapter.rollback()


__all__ = ['AsyncMSSQLTableAdapter']
