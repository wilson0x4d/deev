# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Generator, Generic, Optional, TypeVar, cast, get_args, get_origin
from uuid import UUID

from ..common.DbContext import DbContext
from ..common.DbCursor import DbCursor
from ..common.DbError import DbError
from ..common.DbParams import DbParams
from ..common.DbTypeMapper import DbTypeMapper
from ..entities import EntitySpec, get_entity_spec
from ..translation import hydrate, to_pyobject, splat
from .SqliteProxyConnection import SqliteProxyConnection
from .SqliteTransactionContext import SqliteTransactionContext
from .SqliteTypeMapper import SqliteTypeMapper

TEntity = TypeVar('TEntity')


class SqliteTableAdapter(Generic[TEntity]):

    __column_names: str  # NOTE: just an optimization so we don't have to concat over and over
    __context: DbContext
    __create_table: bool
    __cursor: DbCursor
    __initialized: bool
    __dbtype_mapper: DbTypeMapper
    __entity_spec: EntitySpec
    __transaction_state: int
    __table_name: Optional[str]

    def __init__(
        self,
        context: DbContext,
        *,
        create_table: Optional[bool] = False,
        table_name: Optional[str] = None
    ) -> None:
        self.__context = context if isinstance(context, (SqliteProxyConnection, SqliteTransactionContext)) else SqliteProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name
        self.__transaction_state = 0

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'[{k}]' for k in self.__entity_spec.fields.keys()])
            self.__dbtype_mapper = SqliteTypeMapper(self.__entity_spec)
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
            cast(type, self.__entity_spec.attrs.get(key)))

    def __get_typearg(self, obj: object) -> type:
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is SqliteTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. SqliteTableAdapter[MyEntity]().'
        )

    def create_table(self) -> None:
        """Utility method for creating the target table."""
        self.__deferred_init()
        sql: str = ''
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        if len(self.__entity_spec.primary_key) == 1:
            # handling a single-column PK
            primary_key = self.__entity_spec.primary_key[0]
            id_dbtype = self.__dbtype_mapper.get_provider_type(primary_key)
            columns = ', '.join([
                f'[{k}] {self.__dbtype_mapper.get_provider_type(k)}'
                for k in self.__entity_spec.attrs.keys()
                if k != primary_key
            ])
            sql = f'CREATE TABLE IF NOT EXISTS [{table_name}] ({primary_key} {id_dbtype} PRIMARY KEY{" AUTOINCREMENT" if id_dbtype == "INTEGER" else ""}, {columns})'
        else:
            # special handling of multi-column PK
            columns = ', '.join([
                f'[{k}] {self.__dbtype_mapper.get_provider_type(k)}'
                for k in self.__entity_spec.attrs.keys()
            ])
            primary_key = (
                f", PRIMARY KEY ({','.join(self.__entity_spec.primary_key)})"
                if len(self.__entity_spec.primary_key) > 0
                else ''
            )
            sql = f'CREATE TABLE IF NOT EXISTS [{table_name}] ({columns}{primary_key})'
        self.__execute(sql)

    def commit(self) -> None:
        self.__context.commit()

    def rollback(self) -> None:
        self.__context.rollback()

    def create(self, entity: Optional[TEntity] = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided attributes/values.

        :returns: the primary key of the created entity.
        """
        self.__deferred_init()

        data = (
            splat(entity, to_sql=True)
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
        column_names = ', '.join([f'[{k}]' for k in data.keys()])
        parms = ', '.join(['%?'] * len(data.keys()))
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'INSERT INTO [{table_name}] ({column_names}) VALUES ({parms})'
        params = tuple([
            p.hex if type(p) is UUID else p
            for p in data.values()])
        cursor.execute(sql, params)
        if self.__entity_spec.has_autoincrement:
            v = cursor.lastrowid  # type: ignore[attr-defined]
            if v is not None:
                pk_values[self.__entity_spec.primary_key[0]] = self.__get_pyobject('id', v)
            else:
                raise DbError('Unsupported NULL encountered in primary key.')
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
        where = ' AND '.join([f'[{k}] = %?' for k in pk_values.keys()])
        keys = pk_values.values()
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM [{table_name}] WHERE {where}'
        cursor.execute(sql, tuple(keys))
        data = cursor.fetchone()
        if data:
            if cursor.description is None:
                raise DbError('Provider did not provide a description.')
            result = {}
            for kvp in zip(cursor.description, data):
                value = self.__get_pyobject(kvp[0][0], kvp[1])
                if value is not None:
                    result[kvp[0][0]] = value
            return hydrate(self.__entity_spec.entity_type(), result, from_sql=True)
        else:
            return None

    def update(self, entity: TEntity) -> None:
        self.__deferred_init()
        entity_data = splat(entity, to_sql=True)
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in entity_data.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        _set = ', '.join([
            f'{key} = %?'
            for key in entity_data.keys()
            if key not in self.__entity_spec.primary_key
        ])
        parms = [k for k, v in entity_data.items() if k not in self.__entity_spec.primary_key]
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor.execute(f'UPDATE [{table_name}] SET {_set} WHERE {where}', tuple(parms) + tuple(keys))

    def delete(self, **kwargs: Any) -> None:
        self.__deferred_init()
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'DELETE FROM [{table_name}] WHERE {where}'
        cursor = self.__context.cursor()
        cursor.execute(sql, tuple(keys))

    def exists(self, **kwargs: Any) -> bool:
        self.__deferred_init()
        primary_key = {
            k: (v.hex if type(v) is UUID else v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor = self.__context.cursor()
        cursor.execute(f'SELECT 1 FROM [{table_name}] WHERE {where} LIMIT 1', tuple(keys))
        return cursor.fetchone() is not None

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        self.__deferred_init()
        entity_data = splat(entity, to_sql=True)
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
                f'[{k}]'
                for k in entity_data.keys()
            ])
            update = ', '.join([
                f'[{k}]=%?'
                for k in entity_data.keys()
                if k not in primary_key
            ])
            parms = tuple([
                v.hex if type(v) is UUID else v
                for k, v in entity_data.items()
                if k not in primary_key
            ])
            where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
            values = ', '.join(['%?'] * (len(parms) + len(primary_key)))
            cursor = self.__context.cursor()
            table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
            if len(where) > 0:
                cursor.execute(f'UPDATE [{table_name}] SET {update} WHERE {where}', parms + tuple(primary_key.values()))
            cursor.execute(f'INSERT OR IGNORE INTO [{table_name}] ({cols}) VALUES ({values})', tuple(entity_data.values()))
            return primary_key

    def query(
        self,
        where: Optional[str] = None,
        params: Optional[DbParams] = None,
        orderby: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Generator[TEntity, None, None]:
        self.__deferred_init()
        if params is not None:
            params = [
                p.hex if type(p) is UUID else p
                for p in params
            ]
        else:
            params = []
        where = f' WHERE {where}' if where is not None and len(where) > 0 else ''
        orderby = f' ORDER BY {orderby}' if orderby is not None and len(orderby) > 0 else ''
        limit_str = f' LIMIT {limit}' if limit is not None and limit > 0 else ''
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {self.__column_names} FROM [{table_name}]{where}{orderby}{limit_str}'
        cursor = self.__context.cursor()
        if cursor.description is None:
            Exception('cursor missing required descriptor')
        cursor.execute(sql, tuple(params))
        row = cursor.fetchone()
        while row is not None:
            if cursor.description is None:
                raise DbError('Provider did not provide a description.')
            result = {}
            for kvp in zip(cursor.description, row):
                value = self.__get_pyobject(kvp[0][0], kvp[1])
                if value is not None:
                    result[kvp[0][0]] = value
            yield hydrate(self.__entity_spec.entity_type(), result, from_sql=True)
            row = cursor.fetchone()


__all__ = ['SqliteTableAdapter']
