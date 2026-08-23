# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from clickhouse_connect.driver.client import Client
import hanaro
import logging
import re
from typing import (
    Any,
    Generator,
    Generic,
    Sequence,
    TypeVar,
    cast,
    get_args,
    get_origin,
)
from uuid import UUID

from ..common.db_connection import DbConnection
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_params import DbParams
from ..entities import EntitySpec, get_entity_spec
from ..translation import hydrate, splat, to_pyobject
from .clickhouse_proxy_connection import ClickHouseProxyConnection
from .clickhouse_transaction_context import ClickHouseTransactionContext


TEntity = TypeVar('TEntity')


class ClickHouseTableAdapter(Generic[TEntity]):
    __column_names: str
    __context: DbConnection
    __create_table: bool
    __cursor: DbCursor
    __entity_spec: EntitySpec
    __initialized: bool
    __logger: logging.Logger
    __table_name: str | None
    __transaction_state: int

    def __init__(
        self,
        context: ClickHouseProxyConnection | ClickHouseTransactionContext,
        *,
        create_table: bool | None = False,
        table_name: str | None = None,
        sync_replicas: bool | None = False,
    ) -> None:
        self.__context = context.connection if isinstance(context, ClickHouseTransactionContext) else context  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name
        self.__transaction_state = 0
        self.__is_sync_replicas_enabled = sync_replicas is True and getattr(self.__context, 'is_replicated', False) is True
        self.__logger = hanaro.get_logger()

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
            self.__initialized = True
            if self.__create_table is True:
                self.create_table()

    def sync_replicas(self) -> None:
        """Force all ClickHouse replicas to sync for the current table."""
        if self.__is_sync_replicas_enabled:
            table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
            self.clickhouse_client.command(f'SYSTEM SYNC REPLICA `{table_name}` IF EXISTS')  # type: ignore[attr-defined]

    @property
    def clickhouse_client(self) -> Client:
        return getattr(self.__context, 'clickhouse_client')

    @property
    def primary_key(self) -> tuple[str, ...]:
        return self.__entity_spec.primary_key

    def __execute(self, sql: str, params: DbParams | None = None) -> None:
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

    def create_table(self, *, engine: str | None = None, order_by: str | None = None, partition_by: str | None = None) -> None:
        """
        Create the target table if it does not exist.
        """
        self.__deferred_init()

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
            self.__execute(stmt)
        self.sync_replicas()
        self.__create_table = False

    def commit(self) -> None:
        self.__context.commit()

    def rollback(self) -> None:
        self.__context.rollback()

    def create(self, entity: TEntity | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record.

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
        rows = self.__to_columnar(data, column_names)
        try:
            client = getattr(self.__context, 'clickhouse_client')
            client.insert(
                table=table_name,
                data=rows,
                column_names=column_names
            )
            self.sync_replicas()
        except Exception as e:
            raise DbError(f'ClickHouse insert failed: {e}') from e

        return pk_values

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the primary key represented by ``kwargs``.
        """
        self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}` WHERE {where}'
        pyformat_sql, pyformat_params = self.__hex_and_to_pyformat(sql, keys)
        client = self.clickhouse_client
        try:
            result = client.query(pyformat_sql, parameters=pyformat_params)  # type: ignore[attr-defined]
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

    def update(self, entity: TEntity) -> None:
        """
        Performs a mutation-style update via ``ALTER TABLE ... UPDATE``.

        **Warning**: In ClickHouse, updates are **mutations** — they rewrite entire
        data parts and are **asynchronous** and **expensive** operations.
        This should only be used for infrequent corrections, not in hot paths.
        """
        self.__deferred_init()
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
        self.__execute(sql, tuple(params))
        self.sync_replicas()

    def delete(self, **kwargs: Any) -> None:
        """
        Performs a mutation-style delete via ``ALTER TABLE ... DELETE``.

        **Warning**: In ClickHouse, deletes are **mutations** — they rewrite entire
        data parts and are **asynchronous** and **expensive** operations.
        This should only be used for infrequent corrections, not in hot paths.
        """
        self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'ALTER TABLE `{table_name}` DELETE WHERE {where}'
        self.__execute(sql, keys)

    def exists(self, **kwargs: Any) -> bool:
        """
        Checks whether a record with the given primary key exists.
        """
        self.__deferred_init()
        where, keys = self.__build_where_clause(kwargs)
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT 1 FROM `{table_name}` WHERE {where} LIMIT 1'
        pyformat_sql, pyformat_params = self.__hex_and_to_pyformat(sql, keys)
        client = self.clickhouse_client
        try:
            result = client.query(pyformat_sql, parameters=pyformat_params)  # type: ignore[attr-defined]
            rows = list(result.named_results())  # type: ignore[attr-defined]
            return len(rows) > 0
        except Exception as e:
            raise DbError(f'ClickHouse exists check failed: {e}') from e

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Upserts a record. Checks if the primary key exists and updates,
        otherwise inserts via ``create()``.

        **Warning**: In ClickHouse, updates are **mutations** via ``ALTER TABLE
        UPDATE``, which rewrite data parts and are expensive, asynchronous
        operations. Use ``engine=ReplacingMergeTree`` in ``create_table()``
        for better upsert performance on large tables.
        """
        self.__deferred_init()
        entity_data = splat(entity, to_sql=True)
        if self.__entity_spec.has_autoincrement and entity_data.get(self.__entity_spec.primary_key[0], None) is None:
            return self.create(entity)
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in entity_data.items()
            if k in self.__entity_spec.primary_key
        }
        if self.exists(**primary_key):
            self.update(entity)
        else:
            self.create(entity)
        return primary_key

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
            all_rows.extend(self.__to_columnar(data, column_names))
            pk_values_list.append({
                k: v
                for k, v in data.items()
                if k in self.__entity_spec.primary_key
            })

        try:
            client = getattr(self.__context, 'clickhouse_client')
            client.insert(
                table=table_name,
                data=all_rows,
                column_names=column_names
            )
            self.sync_replicas()
        except Exception as e:
            raise DbError(f'ClickHouse bulk insert failed: {e}') from e

        return pk_values_list

    def query(
        self,
        where: str | None = None,
        params: DbParams | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> Generator[TEntity, None, None]:
        """
        Queries records using a standard ``SELECT`` statement.
        """
        self.__deferred_init()
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
            result = client.query(pyformat_sql, parameters=pyformat_params or None)  # type: ignore[attr-defined]
            for row in result.named_results():  # type: ignore[attr-defined]
                raw: dict[str, Any] = {}
                for key, value in row.items():
                    if value is not None:
                        raw[key] = self.__get_pyobject(key, value)
                yield hydrate(self.__entity_spec.entity_type(), raw, from_sql=True)
        except Exception as e:
            raise DbError(f'ClickHouse query failed: {e}') from e


__all__ = ['ClickHouseTableAdapter']
