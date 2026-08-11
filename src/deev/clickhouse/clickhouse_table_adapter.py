# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import re
from typing import (
    Any,
    Generator,
    Generic,
    Optional,
    Sequence,
    TypeVar,
    cast,
    get_args,
    get_origin,
)
from uuid import UUID

import hanaro

from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_params import DbParams
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec, IndexOptions, IndexOrder, get_entity_spec
from ..translation import hydrate, splat, to_pyobject
from .clickhouse_proxy_connection import ClickHouseProxyConnection
from .clickhouse_transaction_context import ClickHouseTransactionContext
from .clickhouse_type_mapper import ClickHouseTypeMapper

TEntity = TypeVar('TEntity')


class ClickHouseTableAdapter(Generic[TEntity]):
    __column_names: str
    __context: DbContext
    __create_table: bool
    __cursor: DbCursor
    __entity_spec: EntitySpec
    __initialized: bool
    __logger: logging.Logger
    __dbtype_mapper:DbTypeMapper
    __table_name: Optional[str]
    __transaction_state: int

    def __init__(
        self,
        context: DbContext,
        *,
        create_table: Optional[bool] = False,
        table_name: Optional[str] = None
    ) -> None:
        self.__context = context if isinstance(context, (ClickHouseProxyConnection, ClickHouseTransactionContext)) else ClickHouseProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name
        self.__transaction_state = 0
        self.__logger = hanaro.get_logger()

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
            self.__dbtype_mapper = ClickHouseTypeMapper(self.__entity_spec)
            self.__initialized = True
            if self.__create_table is True:
                self.create_table()

    @property
    def primary_key(self) -> tuple[str, ...]:
        return self.__entity_spec.primary_key

    def __execute(self, sql: str, params: Optional[DbParams] = None) -> None:
        cursor = self.__context.cursor()
        cursor.execute(sql, params)

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
                if get_origin(generic_base) is ClickHouseTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. ClickHouseTableAdapter[MyEntity]().'
        )

    def __build_where_clause(self, kwargs: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
        pk_values: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in self.__entity_spec.primary_key:
                pk_values[k] = v.hex if type(v) is UUID else v
        where = ' AND '.join([f'`{k}` = %?' for k in pk_values.keys()])
        return where, tuple(pk_values.values())

    def __prepare_insert_data(
        self,
        data: dict[str, Any],
        column_names: Sequence[str]
    ) -> list[list[Any]]:
        """Convert entity data dict to list of lists for ClickHouse insert()."""
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

    def __get_client(self) -> Any:
        """Get the underlying clickhouse_connect.Client from the context."""
        return cast(ClickHouseProxyConnection, self.__context).clickhouse_client

    def create_table(self, *, native_options: Optional[str] = None) -> None:
        """
        Create the target table if it does not exist.

        Generates DDL with ``ENGINE = MergeTree()`` (default) or an engine family
        specified via *native_options* (e.g. ``engine=ReplacingMergeTree``).

        :param native_options: Semicolon-separated ``key=value`` pairs for table settings
                               (e.g. ``engine=ReplacingMergeTree;order_by=name``).
        """
        self.__deferred_init()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        primary_key = self.__entity_spec.primary_key
        columns = ', '.join([
            f'`{k}` {self.__dbtype_mapper.get_provider_type(k)}'
            for k in self.__entity_spec.attrs.keys()
        ])

        options = self.__merge_tree_options_from_native_options(native_options) if native_options else {}
        engine = options.get('engine', 'MergeTree')
        order_by = options.get('order_by', None)
        partition_by = options.get('partition_by', None)

        if order_by:
            order_clause = f' ORDER BY ({order_by})'
        elif primary_key:
            if len(primary_key) == 1:
                order_clause = f' ORDER BY ({primary_key[0]})'
            else:
                order_clause = f' ORDER BY ({", ".join(f"`{k}`" for k in primary_key)})'
        else:
            order_clause = ''

        partition_clause = f' PARTITION BY ({partition_by})' if partition_by else ''

        sql = f'CREATE TABLE IF NOT EXISTS `{table_name}` ({columns}) ENGINE = {engine}{order_clause}{partition_clause}'
        self.__execute(sql)

    def commit(self) -> None:
        self.__context.commit()

    def rollback(self) -> None:
        self.__context.rollback()

    def create(self, entity: Optional[TEntity] = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record using ClickHouse's native bulk insert API.

        Uses ``client.insert()`` under the hood for maximum throughput.

        :param entity: An entity instance of type ``TEntity``.
        :param kwargs: Individual field values for the new record.
        :returns: The primary key values of the created record.
        """
        self.__deferred_init()

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
        rows = self.__prepare_insert_data(data, column_names)
        try:
            client = self.__get_client()
            client.insert(
                table=table_name,
                data=rows,
                column_names=column_names
            )
        except Exception as e:
            raise DbError(f'ClickHouse insert failed: {e}') from e

        return pk_values

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by ``kwargs``.
        """
        self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}` WHERE {where}'
        cursor.execute(sql, keys)
        data = cursor.fetchone()
        if data:
            if cursor.description is None:
                raise DbError('Provider did not provide a description.')
            result: dict[str, Any] = {}
            for kvp in zip(cursor.description, data):
                value = self.__get_pyobject(kvp[0][0], kvp[1])
                if value is not None:
                    result[kvp[0][0]] = value
            return hydrate(self.__entity_spec.entity_type(), result, from_sql=True)
        return None

    def update(self, entity: TEntity) -> None:
        """
        Performs a mutation-style update via ``ALTER TABLE ... UPDATE``.

        **Warning**: In ClickHouse, updates are **mutations** — they rewrite entire
        data parts and are **asynchronous** and **expensive** operations.
        This should only be used for infrequent corrections, not in hot paths.
        """
        self.__logger.warning(
            'ClickHouseTableAdapter.update() called — this executes ALTER TABLE UPDATE mutation, '
            'which rewrites data parts and is an expensive, asynchronous operation.'
        )
        self.__deferred_init()
        entity_data = splat(entity, to_sql=True)

        pk_where_parts: list[str] = []
        set_parts: list[str] = []
        params: list[Any] = []

        for key in entity_data.keys():
            if key in self.__entity_spec.primary_key:
                val = entity_data[key].hex if type(entity_data[key]) is UUID else entity_data[key]
                pk_where_parts.append(f'`{key}` = %?')
                params.append(val)
            else:
                set_parts.append(f'`{key}` = %?')
                params.append(entity_data[key])

        where_clause = ' AND '.join(pk_where_parts)
        set_clause = ', '.join(set_parts)

        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'ALTER TABLE `{table_name}` UPDATE {set_clause} WHERE {where_clause}'
        self.__execute(sql, tuple(params))

    def delete(self, **kwargs: Any) -> None:
        """
        Performs a mutation-style delete via ``ALTER TABLE ... DELETE``.

        **Warning**: In ClickHouse, deletes are **mutations** — they rewrite entire
        data parts and are **asynchronous** and **expensive** operations.
        This should only be used for infrequent corrections, not in hot paths.
        """
        self.__logger.warning(
            'ClickHouseTableAdapter.delete() called — this executes ALTER TABLE DELETE mutation, '
            'which rewrites data parts and is an expensive, asynchronous operation.'
        )
        self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'ALTER TABLE `{table_name}` DELETE WHERE {where}'
        self.__execute(sql, keys)

    def exists(self, **kwargs: Any) -> bool:
        self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor.execute(f'SELECT 1 FROM `{table_name}` WHERE {where} LIMIT 1', keys)
        return cursor.fetchone() is not None

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Upserts a record. For ClickHouse, writes the entity via ``create()``.

        For true upsert semantics, use ``engine=ReplacingMergeTree`` in ``create_table()``
        and rely on ClickHouse's background merge process to resolve duplicates.
        """
        self.__deferred_init()
        return self.create(entity)

    def bulk_create(self, entities: Sequence[TEntity]) -> list[dict[str, Any]]:
        """
        Creates multiple records using ClickHouse's native bulk insert.

        Efficiently writes all entities in a single ``client.insert()`` call.

        :param entities: A sequence of entity instances.
        :returns: A list of primary key dictionaries, one per entity.
        """
        self.__deferred_init()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        column_names = list(self.__entity_spec.fields.keys())
        all_rows: list[list[Any]] = []
        pk_values_list: list[dict[str, Any]] = []

        for entity in entities:
            data = splat(entity, to_sql=True)
            all_rows.extend(self.__prepare_insert_data(data, column_names))
            pk_values_list.append({
                k: v
                for k, v in data.items()
                if k in self.__entity_spec.primary_key
            })

        try:
            client = self.__get_client()
            client.insert(
                table=table_name,
                data=all_rows,
                column_names=column_names
            )
        except Exception as e:
            raise DbError(f'ClickHouse bulk insert failed: {e}') from e

        return pk_values_list

    def query(
        self,
        where: Optional[str] = None,
        params: Optional[DbParams] = None,
        orderby: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Generator[TEntity, None, None]:
        """
        Queries records using a standard ``SELECT`` statement.
        """
        self.__deferred_init()
        if params is not None:
            params = [
                p.hex if type(p) is UUID else p
                for p in params
            ]
        else:
            params = []
        where_clause = f' WHERE {where}' if where is not None and len(where) > 0 else ''
        orderby_clause = f' ORDER BY {orderby}' if orderby is not None and len(orderby) > 0 else ''
        limit_str = f' LIMIT {limit}' if limit is not None and limit > 0 else ''
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}`{where_clause}{orderby_clause}{limit_str}'
        cursor = self.__context.cursor()
        if cursor.description is None:
            raise Exception('cursor missing required descriptor')
        cursor.execute(sql, tuple(params))
        row = cursor.fetchone()
        while row is not None:
            if cursor.description is None:
                raise DbError('Provider did not provide a description.')
            result: dict[str, Any] = {}
            for kvp in zip(cursor.description, row):
                value = self.__get_pyobject(kvp[0][0], kvp[1])
                if value is not None:
                    result[kvp[0][0]] = value
            yield hydrate(self.__entity_spec.entity_type(), result, from_sql=True)
            row = cursor.fetchone()


__all__ = ['ClickHouseTableAdapter']
