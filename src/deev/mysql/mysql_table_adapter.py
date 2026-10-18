# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import mysql.connector
import mysql.connector.abstracts
import mysql.connector.cursor
import mysql.connector.types
from typing import Any, Callable, Generator, Generic, TypeVar, cast, get_args, get_origin
from uuid import UUID

from ..common.db_context import DbContext
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec, apply_defaults_for, construct_entity, get_entity_spec
from ..translation import compile_hydrate_plan, splat_mysql, to_pyobject
from .mysql_proxy_connection import MySQLProxyConnection
from .mysql_transaction_context import MySQLTransactionContext
from .mysql_type_mapper import MySQLTypeMapper

TEntity = TypeVar('TEntity')


class MySQLTableAdapter(Generic[TEntity]):
    """
    MySQL implementation of :class:`DbTableAdapter`.

    Provides typed CRUD operations with SQL parameter binding using ``%?`` placeholders
    (translated to ``%s`` at runtime). Supports ``ON DUPLICATE KEY UPDATE`` for upserts.

    :param context: A :class:`MySQLProxyConnection` or :class:`MySQLTransactionContext`.
    :param create_table: Whether to auto-create the table on first operation.
    :param table_name: Optional table name override.
    """

    __column_names: str  # NOTE: just an optimization so we don't have to concat over and over
    __context: DbContext
    __create_table: bool
    __default_only_names: tuple[str, ...]
    __entity_spec: EntitySpec
    __initialized: bool
    __dbtype_mapper: DbTypeMapper
    __hydrate_plan: tuple[tuple[str, Callable[[Any], Any] | None], ...]
    __table_name: str | None

    def __init__(
        self,
        context: DbContext,
        *,
        create_table: bool | None = False,
        table_name: str | None = None
    ) -> None:
        """Initialize the MySQL table adapter."""
        self.__context = context if isinstance(context, (MySQLProxyConnection, MySQLTransactionContext)) else MySQLProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
            self.__hydrate_plan = compile_hydrate_plan(self.__entity_spec, from_mysql=True)
            self.__default_only_names = tuple(name for name, convert in self.__hydrate_plan if convert is None)
            self.__dbtype_mapper = MySQLTypeMapper(self.__entity_spec)
            self.__initialized = True
            if self.__create_table is True:
                self.create_table()

    @property
    def primary_key(self) -> tuple[str, ...]:
        return self.__entity_spec.primary_key

    def __execute(self, sql: str, parameters: DbParameters | None = None) -> None:
        cursor = self.__context.cursor()
        cursor.execute(sql, parameters)

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
                if get_origin(generic_base) is MySQLTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. MySQLTableAdapter[MyEntity]().'
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

    def create_table(self) -> None:
        """Utility method for creating the target table."""
        self.__deferred_init()
        from .mysql_ddl_generator import MySQLDDLGenerator
        ddl_generator = MySQLDDLGenerator()
        ddl = ddl_generator.generate_table_ddl(entity_spec=self.__entity_spec, table_name=self.__table_name)
        for stmt in ddl:
            self.__execute(stmt)
        self.__create_table = False

    def commit(self) -> None:
        self.__context.commit()

    def rollback(self) -> None:
        self.__context.rollback()

    def create(self, entity: TEntity | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided attributes/values.

        :returns: the primary key of the created entity.
        """
        self.__deferred_init()

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
        parms = ', '.join(['%?'] * len(data.keys()))
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'INSERT INTO `{table_name}` ({column_names}) VALUES ({parms})'
        parameters = tuple([
            cast(mysql.connector.types.MySQLConvertibleType, p.hex if type(p) is UUID else p)
            for p in data.values()])
        cursor.execute(sql, parameters)
        if self.__entity_spec.has_autoincrement:
            cursor.execute('SELECT LAST_INSERT_ID()')
            v = cursor.fetchone()
            if v is not None:
                pk_values[self.__entity_spec.primary_key[0]] = self.__get_pyobject('id', v[0])
            else:
                raise Exception('Unsupported NULL encountered in primary key.')
        return pk_values

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the key represented by `kwargs`.
        """
        self.__deferred_init()
        pk_values = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in pk_values.keys()])
        keys = pk_values.values()
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM `{table_name}` WHERE {where}'
        cursor.execute(sql, tuple(keys))
        data = cursor.fetchone()
        if data:
            return self.__hydrate_row(data)
        else:
            return None

    def update(self, entity: TEntity) -> None:
        self.__deferred_init()
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
        parms = [k for k, v in entity_data.items() if k not in self.__entity_spec.primary_key]
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor.execute(f'UPDATE `{table_name}` SET {_set} WHERE {where}', tuple(parms) + tuple(keys))

    def delete(self, **kwargs: Any) -> None:
        self.__deferred_init()
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'DELETE FROM `{table_name}` WHERE {where}'
        cursor = self.__context.cursor()
        cursor.execute(sql, tuple(keys))

    def exists(self, **kwargs: Any) -> bool:
        self.__deferred_init()
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'`{k}` = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor.execute(f'SELECT 1 FROM `{table_name}` WHERE {where} LIMIT 1', tuple(keys))
        return cursor.fetchone() is not None

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        self.__deferred_init()
        entity_data = splat_mysql(entity)
        if self.__entity_spec.has_autoincrement and entity_data.get(self.__entity_spec.primary_key[0], None) is None:
            # no id provided and table is auto-increment, use INSERT syntax for new records
            return self.create(entity)
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
            cursor = self.__context.cursor()
            table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
            sql = f'INSERT INTO `{table_name}` ({cols}) VALUES ({values}) AS V ON DUPLICATE KEY UPDATE {update}'
            cursor.execute(sql, tuple(parms))
            return primary_key

    def query(
        self,
        where: str | None = None,
        parameters: DbParameters | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> Generator[TEntity, None, None]:
        """
        Query records from the table.

        :param where: Optional WHERE clause (without the ``WHERE`` keyword).
        :param parameters: Query parameters for placeholders in ``where``.
        :param orderby: Optional ORDER BY clause (without the ``ORDER BY`` keyword).
        :param limit: Optional LIMIT value.
        :yields: Hydrated entity instances.
        """
        self.__deferred_init()
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
        cursor = self.__context.cursor()
        cursor.execute(sql, tuple(parameters))
        row = cursor.fetchone()
        while row is not None:
            yield self.__hydrate_row(row)
            row = cursor.fetchone()


__all__ = ['MySQLTableAdapter']
