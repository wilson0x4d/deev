# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import mysql.connector
import mysql.connector.types
from typing import Any, AsyncGenerator, Callable, TypeVar, cast, get_args, get_origin
from uuid import UUID

from ..common.async_db_table_adapter import AsyncDbTableAdapter
from ..common.db_context import AsyncDbContext
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..entities import EntitySpec, apply_defaults_for, construct_entity, get_entity_spec, invoke_on_create_table_async
from ..translation import compile_hydrate_plan, splat_mysql, to_pyobject
from .async_mysql_proxy_connection import AsyncMySQLProxyConnection
from .async_mysql_transaction_context import AsyncMySQLTransactionContext
from .mysql_type_mapper import MySQLTypeMapper

TEntity = TypeVar('TEntity')


class AsyncMySQLTableAdapter(AsyncDbTableAdapter[TEntity]):
    """
    Async MySQL implementation of :class:`AsyncDbTableAdapter`.

    Uses native async MySQL driver with ``ON DUPLICATE KEY UPDATE`` for upserts.

    :param context: An :class:`AsyncMySQLProxyConnection` or :class:`AsyncMySQLTransactionContext`.
    :param create_table: Whether to auto-create the table on first operation.
    :param table_name: Optional table name override.
    """

    __column_names: str
    __context: AsyncDbContext
    __create_table: bool
    __default_only_names: tuple[str, ...]
    __entity_spec: EntitySpec
    __initialized: bool
    __dbtype_mapper: MySQLTypeMapper
    __hydrate_plan: tuple[tuple[str, Callable[[Any], Any] | None], ...]
    __table_name: str | None

    def __init__(
        self,
        context: AsyncDbContext,
        *,
        create_table: bool | None = False,
        table_name: str | None = None
    ) -> None:
        """Initialize the async MySQL table adapter."""
        self.__context = context if isinstance(context, (AsyncMySQLProxyConnection, AsyncMySQLTransactionContext)) else AsyncMySQLProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name

    def __resolve_specs(self) -> None:
        self.__entity_spec = get_entity_spec(self.__get_typearg(self))
        self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
        self.__hydrate_plan = compile_hydrate_plan(self.__entity_spec, from_mysql=True)
        self.__default_only_names = tuple(name for name, convert in self.__hydrate_plan if convert is None)
        self.__dbtype_mapper = MySQLTypeMapper(self.__entity_spec)

    async def __deferred_init(self) -> None:
        if not self.__initialized:
            self.__resolve_specs()
            self.__initialized = True
            if self.__create_table is True:
                await self.create_table()

    @property
    def primary_key(self) -> tuple[str, ...]:
        if not self.__initialized:
            self.__resolve_specs()
            self.__initialized = True
        return self.__entity_spec.primary_key

    async def __execute(self, sql: str, parameters: DbParameters | None = None) -> None:
        cursor = await self.__context.cursor()
        await cursor.execute(sql, parameters)

    def __get_pyobject(self, key: str, value: Any) -> Any:
        return to_pyobject(
            value,
            cast(type, self.__entity_spec.attrs.get(key)),
            from_mysql=True)

    def __get_typearg(self, obj: object) -> type:
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is AsyncMySQLTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. AsyncMySQLTableAdapter[MyEntity]().'
        )

    def __hydrate_row(self, row: tuple[Any, ...]) -> TEntity:
        entity = construct_entity(self.__entity_spec.entity_type, ())
        missing: list[str] | None = None
        for i, (name, convert) in enumerate(self.__hydrate_plan):
            if convert is None:
                continue
            value = convert(row[i])
            if value is not None:
                setattr(entity, name, value)
            elif missing is None:
                missing = [name]
            else:
                missing.append(name)
        if missing is not None:
            if self.__default_only_names:
                apply_defaults_for(entity, [*missing, *self.__default_only_names])
            else:
                apply_defaults_for(entity, missing)
        elif self.__default_only_names:
            apply_defaults_for(entity, self.__default_only_names)
        return entity

    async def _do_create_table(self) -> bool:
        """
        Create the target table and its indexes if the table does not already exist.

        :return: ``True`` if the table was created by this call, ``False`` if it already existed.
        """
        await self.__deferred_init()
        from .mysql_ddl_generator import MySQLDDLGenerator
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor = await self.__context.cursor()
        await cursor.execute(
            'SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %? LIMIT 1',
            (table_name,)
        )
        if await cursor.fetchone() is not None:
            return False
        ddl_generator = MySQLDDLGenerator()
        ddl = ddl_generator.generate_table_ddl(entity_spec=self.__entity_spec, table_name=self.__table_name)
        for stmt in ddl:
            await self.__execute(stmt)
        return True

    async def create_table(self) -> None:
        """
        Utility method for creating the target table.

        If the table already exists, no DDL is executed. When the table is created,
        the entity's ``on_create_table`` hook (if defined) is invoked with this adapter;
        async hooks are awaited.
        """
        created = await self._do_create_table()
        if created:
            await invoke_on_create_table_async(self.__entity_spec.entity_type, self)
        self.__create_table = False

    async def commit(self) -> None:
        await self.__context.commit()

    async def rollback(self) -> None:
        await self.__context.rollback()

    async def create(self, entity: TEntity | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided attributes/values.

        :returns: the primary key of the created entity.
        """
        await self.__deferred_init()

        data = (
            splat_mysql(entity)
            if entity is not None
            else dict[str, Any]()
        )
        if kwargs is not None:
            data.update(kwargs)
        pk_values = {
            k: v
            for k, v in data.items()
            if k in self.__entity_spec.primary_key
        }
        if self.__entity_spec.has_autoincrement:
            # special handling for auto-increment columns (we don't want to insert any field marked for autoincrement)
            if self.__entity_spec.primary_key[0] in data.keys():
                data.pop(self.__entity_spec.primary_key[0])
        column_names = ', '.join([f'`{k}`' for k in data.keys()])
        parms = ', '.join(['%?' for _ in data.keys()])
        cursor = await self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'INSERT INTO `{table_name}` ({column_names}) VALUES ({parms})'
        parameters = tuple([
            cast(mysql.connector.types.MySQLConvertibleType, p.hex if type(p) is UUID else p)
            for p in data.values()])
        await cursor.execute(sql, parameters)
        if self.__entity_spec.has_autoincrement:
            await cursor.execute('SELECT LAST_INSERT_ID()')
            v = await cursor.fetchone()
            if v is not None:
                pk_values[self.__entity_spec.primary_key[0]] = self.__get_pyobject('id', v[0])
            else:
                raise Exception('Unsupported NULL encountered in primary key.')
        return pk_values

    async def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the key represented by `kwargs`.
        """
        await self.__deferred_init()
        pk_values = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in pk_values.keys()])
        keys = pk_values.values()
        cursor = await self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}` WHERE {where}'
        await cursor.execute(sql, tuple(keys))
        data = await cursor.fetchone()
        if data:
            return self.__hydrate_row(data)
        else:
            return None

    async def update(self, entity: TEntity) -> None:
        await self.__deferred_init()
        entity_data = splat_mysql(entity)
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in entity_data.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        _set = ', '.join([
            f'`{key}` = %?'
            for key in entity_data.keys()
            if key not in self.__entity_spec.primary_key
        ])
        parms = [v for k, v in entity_data.items() if k not in self.__entity_spec.primary_key]
        cursor = await self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        await cursor.execute(f'UPDATE `{table_name}` SET {_set} WHERE {where}', tuple(parms) + tuple(keys))

    async def delete(self, **kwargs: Any) -> None:
        await self.__deferred_init()
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'DELETE FROM `{table_name}` WHERE {where}'
        cursor = await self.__context.cursor()
        await cursor.execute(sql, tuple(keys))

    async def exists(self, **kwargs: Any) -> bool:
        await self.__deferred_init()
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        cursor = await self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        await cursor.execute(f'SELECT 1 FROM `{table_name}` WHERE {where} LIMIT 1', tuple(keys))
        return (await cursor.fetchone()) is not None

    async def upsert(self, entity: TEntity) -> dict[str, Any]:
        await self.__deferred_init()
        entity_data = splat_mysql(entity)
        pk_value = entity_data.get(self.__entity_spec.primary_key[0], None)
        if self.__entity_spec.has_autoincrement and pk_value in (None, 0):
            return await self.create(entity)
        else:
            # in all other cases, use values provided for upsertion
            primary_key = {
                k: (v.hex if type(v) is UUID else v)
                for k, v in entity_data.items()
                if k in self.__entity_spec.primary_key
            }
            cols = ', '.join([
                f'`{k}`'
                for k in entity_data.keys()
            ])
            update = ', '.join([
                f'`{k}`=V.`{k}`'
                for k in entity_data.keys()
                if k not in primary_key
            ])
            parms = [
                v.hex if type(v) is UUID else v
                for k, v in entity_data.items()
            ]
            values = ', '.join(['%?'] * len(parms))
            cursor = await self.__context.cursor()
            table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
            sql = f'INSERT INTO `{table_name}` ({cols}) VALUES ({values}) AS V ON DUPLICATE KEY UPDATE {update}'
            await cursor.execute(sql, tuple(parms))
            return primary_key

    async def query(  # type: ignore[override]
        self,
        where: str | None = None,
        parameters: DbParameters | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> AsyncGenerator[TEntity, None]:
        await self.__deferred_init()
        if parameters is not None:
            parameters = [
                p.hex if type(p) is UUID else p
                for p in parameters
            ]
        else:
            parameters = []
        where = f' WHERE {where}' if where is not None and len(where) > 0 else ''
        orderby = f' ORDER BY {orderby}' if orderby is not None and len(orderby) > 0 else ''
        limit_str = f' LIMIT {limit}' if limit is not None and limit > 0 else ''
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}`{where}{orderby}{limit_str}'
        cursor = await self.__context.cursor()
        await cursor.execute(sql, tuple(parameters))
        row = await cursor.fetchone()
        while row is not None:
            yield self.__hydrate_row(row)
            row = await cursor.fetchone()


__all__ = ['AsyncMySQLTableAdapter']
