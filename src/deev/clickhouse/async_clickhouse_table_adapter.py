# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from clickhouse_connect.driver import AsyncClient
import hanaro
import logging
import re
from typing import (
    Any,
    AsyncGenerator,
    Sequence,
    TypeVar,
    cast,
    get_args,
    get_origin,
)
from uuid import UUID


from ..common.async_db_table_adapter import AsyncDbTableAdapter
from ..common.async_db_connection import AsyncDbConnection
from ..common.db_context import AsyncDbContext
from ..common.db_error import DbError
from ..common.db_params import DbParams
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec, get_entity_spec
from ..translation import hydrate, splat, to_pyobject


from .async_clickhouse_transaction_context import AsyncClickHouseTransactionContext
from .clickhouse_type_mapper import ClickHouseTypeMapper


TEntity = TypeVar('TEntity')


class AsyncClickHouseTableAdapter(AsyncDbTableAdapter[TEntity]):
    __column_names: str
    __context: AsyncDbConnection
    __create_table: bool
    __entity_spec: EntitySpec
    __initialized: bool
    __logger: logging.Logger
    __dbtype_mapper: DbTypeMapper
    __table_name: str | None
    __transaction_state: int

    def __init__(
        self,
        context: AsyncDbContext,
        *,
        create_table: bool | None = False,
        table_name: str | None = None,
        sync_replicas: bool | None = False,
    ) -> None:
        self.__context = context.connection if isinstance(context, AsyncClickHouseTransactionContext) else context  # type: ignore[arg-type, assignment]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name
        self.__transaction_state = 0
        self.__is_sync_replicas_enabled = sync_replicas is True and getattr(self.__context, 'is_replicated', False) is True
        self.__logger = hanaro.get_logger()

    async def __deferred_init(self) -> None:
        if not self.__initialized:
            self.__initialized = True
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
            self.__dbtype_mapper = ClickHouseTypeMapper(self.__entity_spec)
            if self.__create_table is True:                
                await self.create_table()

    async def sync_replicas(self) -> None:
        """Force all ClickHouse replicas to sync for the current table."""
        if self.__is_sync_replicas_enabled:
            table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
            await self.clickhouse_client.command(f'SYSTEM SYNC REPLICA `{table_name}` IF EXISTS')  # type: ignore[attr-defined]

    @property
    def clickhouse_client(self) -> AsyncClient:
        return getattr(self.__context, 'clickhouse_client')

    @property
    def primary_key(self) -> tuple[str, ...]:
        return self.__entity_spec.primary_key

    async def __execute(self, sql: str, params: DbParams | None = None) -> None:
        cursor = await self.__context.cursor()
        await cursor.execute(sql, params)

    def __get_pyobject(self, key: str, value: Any) -> Any:
        return to_pyobject(
            value,
            cast(type, self.__entity_spec.attrs.get(key))
        )

    def __get_typearg(self, obj: object) -> type:
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is AsyncClickHouseTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. AsyncClickHouseTableAdapter[MyEntity]().'
        )

    def __build_where_clause(self, kwargs: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
        pk_values: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in self.__entity_spec.primary_key:
                pk_values[k] = v.hex if type(v) is UUID else v
        where = ' AND '.join([f'`{k}` = %?' for k in pk_values.keys()])
        return where, tuple(pk_values.values())

    def __hexify(self, value: Any) -> Any:
        return value.hex if isinstance(value, UUID) else value

    def __hex_and_to_pyformat(
        self,
        sql: str,
        params: Sequence[Any]
    ) -> tuple[str, dict[str, Any]]:
        """Convert %? placeholders to pyformat params, applying UUID hex conversion."""
        param_dict: dict[str, Any] = {}
        result: list[str] = []
        i = 0
        for part in re.split(r'(%\?)', sql):
            if part == '%?':
                name = f'p{i}'
                param_dict[name] = self.__hexify(params[i])
                result.append(f'(%({name})s)')
                i += 1
            else:
                result.append(part)
        return ''.join(result), param_dict

    def __to_columnar(
        self,
        data: dict[str, Any],
        column_names: Sequence[str]
    ) -> list[list[Any]]:
        """Convert entity data dict to columnar structure (list of lists) for ClickHouse native calls."""
        row = []
        for col in column_names:
            val = data.get(col)
            row.append(val.hex if type(val) is UUID else val)
        return [row]

    def __merge_tree_options_from_native_options(self, native_options: str) -> dict[str, str]:
        if not native_options or not native_options.strip():
            return {}
        options: dict[str, str] = {}
        for pair in native_options.split(';'):
            pair = pair.strip()
            if '=' in pair:
                key, value = pair.split('=', 1)
                options[key.strip()] = value.strip()
        return options

    async def create_table(self, *, engine: str | None = None, order_by: str | None = None, partition_by: str | None = None) -> None:
        """
        Create the target table if it does not exist.
        """
        from .clickhouse_ddl_generator import ClickHouseDDLGenerator
        ddl_generator = ClickHouseDDLGenerator()
        ddl = ddl_generator.generate_table_ddl(
            table_name=self.__table_name,
            entity_spec=self.__entity_spec,
            engine=engine,
            order_by=order_by,
            partition_by=partition_by
        )
        for stmt in ddl:
            await self.__execute(stmt)
        self.__create_table = False

    async def commit(self) -> None:
        await self.__context.commit()  # type: ignore[attr-defined]

    async def rollback(self) -> None:
        await self.__context.rollback()  # type: ignore[attr-defined]

    async def create(self, entity: TEntity | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record.

        :param entity: An entity instance of type ``TEntity``.
        :param kwargs: Individual field values for the new record.
        :returns: The primary key values of the created record.
        """
        await self.__deferred_init()

        data = (
            splat(entity, to_sql=True)
            if entity is not None
            else dict[str, Any]()
        )
        if kwargs is not None:
            data.update(kwargs)

        pk_values: dict[str, Any] = {
            k: v
            for k, v in data.items()
            if k in self.__entity_spec.primary_key
        }

        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        column_names = list(self.__entity_spec.fields.keys())
        rows = self.__to_columnar(data, column_names)
        try:
            client = getattr(self.__context, 'clickhouse_client')
            await client.insert(  # type: ignore[attr-defined]
                table=table_name,
                data=rows,
                column_names=column_names
            )
            await self.sync_replicas()
        except Exception as e:
            raise DbError(f'ClickHouse insert failed: {e}') from e

        return pk_values

    async def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by ``kwargs``.
        """
        await self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}` WHERE {where}'
        pyformat_sql, pyformat_params = self.__hex_and_to_pyformat(sql, keys)
        client = self.clickhouse_client
        try:
            result = await client.query(pyformat_sql, parameters=pyformat_params)  # type: ignore[attr-defined]
            rows = list(result.named_results())  # type: ignore[attr-defined]
            if rows:
                raw: dict[str, Any] = {}
                for key, value in rows[0].items():
                    if value is not None:
                        raw[key] = self.__get_pyobject(key, value)
                return hydrate(self.__entity_spec.entity_type(), raw, from_sql=True)
            return None
        except Exception as e:
            raise DbError(f'ClickHouse read failed: {e}') from e

    async def update(self, entity: TEntity) -> None:
        """
        Performs a mutation-style update via ``ALTER TABLE ... UPDATE``.

        **Warning**: In ClickHouse, updates are **mutations** — they rewrite entire
        data parts and are **asynchronous** and **expensive** operations.
        This should only be used for infrequent corrections, not in hot paths.
        """
        await self.__deferred_init()
        entity_data = splat(entity, to_sql=True)

        set_parts: list[str] = []
        pk_where_parts: list[str] = []
        params: list[Any] = []

        for key in entity_data.keys():
            if key not in self.__entity_spec.primary_key:
                set_parts.append(f'`{key}` = %?')
                params.append(entity_data[key])

        for key in entity_data.keys():
            if key in self.__entity_spec.primary_key:
                pk_where_parts.append(f'`{key}` = %?')
                params.append(entity_data[key])

        where_clause = ' AND '.join(pk_where_parts)
        set_clause = ', '.join(set_parts)

        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'ALTER TABLE `{table_name}` UPDATE {set_clause} WHERE {where_clause}'
        await self.__execute(sql, tuple(params))
        await self.sync_replicas()

    async def delete(self, **kwargs: Any) -> None:
        """
        Performs a mutation-style delete via ``ALTER TABLE ... DELETE``.

        **Warning**: In ClickHouse, deletes are **mutations** — they rewrite entire
        data parts and are **asynchronous** and **expensive** operations.
        This should only be used for infrequent corrections, not in hot paths.
        """
        await self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'ALTER TABLE `{table_name}` DELETE WHERE {where}'
        await self.__execute(sql, keys)

    async def exists(self, **kwargs: Any) -> bool:
        """
        Checks whether a record with the given primary key exists.
        """
        await self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT 1 FROM `{table_name}` WHERE {where} LIMIT 1'
        pyformat_sql, pyformat_params = self.__hex_and_to_pyformat(sql, keys)
        client = self.clickhouse_client
        try:
            result = await client.query(pyformat_sql, parameters=pyformat_params)  # type: ignore[attr-defined]
            rows = list(result.named_results())  # type: ignore[attr-defined]
            return len(rows) > 0
        except Exception as e:
            raise DbError(f'ClickHouse exists check failed: {e}') from e

    async def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Upserts a record. Checks if the primary key exists and updates,
        otherwise inserts via ``create()``.

        **Warning**: In ClickHouse, updates are **mutations** via ``ALTER TABLE
        UPDATE``, which rewrite data parts and are expensive, asynchronous
        operations. Use ``engine=ReplacingMergeTree`` in ``create_table()``
        for better upsert performance on large tables.
        """
        await self.__deferred_init()
        entity_data = splat(entity, to_sql=True)
        if self.__entity_spec.has_autoincrement and entity_data.get(self.__entity_spec.primary_key[0], None) is None:
            return await self.create(entity)
        if await self.exists(
            **{k: v for k, v in entity_data.items() if k in self.__entity_spec.primary_key}
        ):
            await self.update(entity)
        else:
            await self.create(entity)
        return {
            k: (v.hex if type(v) is UUID else v)
            for k, v in entity_data.items()
            if k in self.__entity_spec.primary_key
        }

    async def bulk_create(self, entities: Sequence[TEntity]) -> list[dict[str, Any]]:
        """
        Creates multiple records using ClickHouse's native bulk insert.

        Efficiently writes all entities in a single ``client.insert()`` call.

        :param entities: A sequence of entity instances.
        :returns: A list of primary key dictionaries, one per entity.
        """
        await self.__deferred_init()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        column_names = list(self.__entity_spec.fields.keys())
        all_rows: list[list[Any]] = []
        pk_values_list: list[dict[str, Any]] = []

        for entity in entities:
            data = splat(entity, to_sql=True)
            all_rows.extend(self.__to_columnar(data, column_names))
            pk_values_list.append({
                k: v
                for k, v in data.items()
                if k in self.__entity_spec.primary_key
            })

        try:
            client = getattr(self.__context, 'clickhouse_client')
            await client.insert(  # type: ignore[attr-defined]
                table=table_name,
                data=all_rows,
                column_names=column_names
            )
            await self.sync_replicas()
        except Exception as e:
            raise DbError(f'ClickHouse bulk insert failed: {e}') from e

        return pk_values_list

    async def query(  # type: ignore[override]
        self,
        where: str | None = None,
        params: DbParams | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> AsyncGenerator[TEntity, None]:
        """
        Queries records using a standard ``SELECT`` statement.
        """
        await self.__deferred_init()
        where_clause = f' WHERE {where}' if where is not None and len(where) > 0 else ''
        orderby_clause = f' ORDER BY {orderby}' if orderby is not None and len(orderby) > 0 else ''
        limit_str = f' LIMIT {limit}' if limit is not None and limit > 0 else ''
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}`{where_clause}{orderby_clause}{limit_str}'
        if params is not None:
            pyformat_sql, pyformat_params = self.__hex_and_to_pyformat(sql, [p for p in params])
        else:
            pyformat_sql, pyformat_params = sql, {}
        client = self.clickhouse_client
        try:
            result = await client.query(pyformat_sql, parameters=pyformat_params or None)  # type: ignore[attr-defined]
            for row in result.named_results():
                raw: dict[str, Any] = {}
                for key, value in row.items():
                    if value is not None:
                        raw[key] = self.__get_pyobject(key, value)
                yield hydrate(self.__entity_spec.entity_type(), raw, from_sql=True)
        except Exception as e:
            raise DbError(f'ClickHouse query failed: {e}') from e


__all__ = ['AsyncClickHouseTableAdapter']
