# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Generator, Generic, TypeVar, cast, get_args, get_origin
from uuid import UUID

from ..common.db_context import DbContext
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec, get_entity_spec
from ..translation import hydrate, to_pyobject, splat
from .mssql_proxy_connection import MSSQLProxyConnection
from .mssql_transaction_context import MSSQLTransactionContext
from .mssql_type_mapper import MSSQLTypeMapper

TEntity = TypeVar('TEntity')


class MSSQLTableAdapter(Generic[TEntity]):
    """
    Table adapter for Microsoft SQL Server that provides CRUD operations for entities.
    """

    __column_names: str
    __context: DbContext
    __create_table: bool
    __entity_spec: EntitySpec
    __initialized: bool
    __dbtype_mapper: DbTypeMapper
    __table_name: str | None

    def __init__(
        self,
        context: DbContext,
        *,
        create_table: bool | None = False,
        table_name: str | None = None
    ) -> None:
        """
        Initialize a new MSSQLTableAdapter.

        :param context: A :class:`DbContext` or :class:`MSSQLProxyConnection` instance.
        :param create_table: Whether to create the table if it does not exist.
        :param table_name: Optional override for the table name.
        """
        self.__context = context if isinstance(context, (MSSQLProxyConnection, MSSQLTransactionContext)) else MSSQLProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'[{k}]' for k in self.__entity_spec.fields.keys()])
            self.__dbtype_mapper = MSSQLTypeMapper(self.__entity_spec)
            self.__initialized = True
            if self.__create_table is True:
                self.create_table()

    @property
    def primary_key(self) -> tuple[str, ...]:
        """
        Get the primary key column names for the entity.

        :returns: A tuple of primary key column names.
        """
        self.__deferred_init()
        return self.__entity_spec.primary_key

    def __execute(self, sql: str, parameters: DbParameters | None = None) -> None:
        """
        Execute a SQL statement with optional parameters.

        :param sql: The SQL statement to execute.
        :param parameters: Optional parameters to bind to the statement.
        """
        cursor = self.__context.cursor()
        cursor.execute(sql, parameters)

    def __get_pyobject(self, key: str, value: Any) -> Any:
        """
        Convert a SQL value to the appropriate Python object type.

        :param key: The field name.
        :param value: The raw value from the database.
        :returns: The converted Python object.
        """
        return to_pyobject(
            value,
            cast(type, self.__entity_spec.attrs.get(key)))

    @staticmethod
    def __to_mssql_value(value: Any) -> Any:
        """
        Convert a Python value to an MSSQL-compatible format.

        :param value: The Python value to convert.
        :returns: The MSSQL-compatible value.
        """
        if type(value) is UUID:
            return str(value)
        return value

    def __get_typearg(self, obj: object) -> type:
        """
        Extract the type argument from a generic MSSQLTableAdapter instance.

        :param obj: The object to inspect.
        :returns: The entity type.
        :raises RuntimeError: If the type argument cannot be determined.
        """
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is MSSQLTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. MSSQLTableAdapter[MyEntity]().'
        )

    def create_table(self) -> None:
        """
        Create the target table if it does not already exist.

        Generates the table DDL using :class:`MSSQLDDLGenerator` and executes it.
        """
        self.__deferred_init()
        from .mssql_ddl_generator import MSSQLDDLGenerator
        ddl_generator = MSSQLDDLGenerator()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        # Check if table already exists (SQL Server has no IF NOT EXISTS on CREATE TABLE)
        cursor = self.__context.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sys.tables WHERE name = %? AND schema_name(schema_id) = 'dbo'",
            (table_name,)
        )
        result = cursor.fetchone()
        if result is not None and result[0] == 0:
            ddl = ddl_generator.generate_table_ddl(entity_spec=self.__entity_spec, table_name=self.__table_name)
            for stmt in ddl:
                self.__execute(stmt)
        self.__create_table = False

    def commit(self) -> None:
        """Commit the current transaction."""
        self.__context.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.__context.rollback()

    def create(self, entity: TEntity | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided attributes/values.

        :param entity: The entity to create.
        :param kwargs: Additional attribute values to include.
        :returns: A dictionary containing the primary key values of the created entity.
        """
        self.__deferred_init()

        data = (
            splat(entity, to_mssql=True)
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
            if self.__entity_spec.primary_key[0] in data.keys():
                data.pop(self.__entity_spec.primary_key[0])
        column_names = ', '.join([f'[{k}]' for k in data.keys()])
        parms = ', '.join(['%?' for _ in data.keys()])
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        if self.__entity_spec.has_autoincrement:
            sql = f'INSERT INTO [{table_name}] ({column_names}) OUTPUT INSERTED.[{self.__entity_spec.primary_key[0]}] VALUES ({parms})'
            parameters = tuple(data.values())
            cursor.execute(sql, parameters)
            v = cursor.fetchone()
            if v is not None:
                pk_values[self.__entity_spec.primary_key[0]] = self.__get_pyobject(self.__entity_spec.primary_key[0], int(v[0]))
            else:
                raise Exception('Unsupported NULL encountered in primary key.')
        else:
            sql = f'INSERT INTO [{table_name}] ({column_names}) VALUES ({parms})'
            parameters = tuple(data.values())
            cursor.execute(sql, parameters)
        # For non-autoincrement PKs, fetch the inserted row's PK value
        if not pk_values:
            raise DbError('No primary key values provided for non-autoincrement entity.')
        cursor.execute(f'SELECT TOP 1 1 FROM [{table_name}] WHERE {" AND ".join([f"[{k}] = ?" for k in pk_values.keys()])}', tuple(pk_values.values()))
        if cursor.fetchone() is None:
            raise DbError('Failed to verify created entity exists.')
        return pk_values

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table using primary key values.

        :param kwargs: Primary key values to filter by.
        :returns: The hydrated entity if found, otherwise ``None``.
        """
        self.__deferred_init()
        pk_values = {
            k: self.__to_mssql_value(v)
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
            return hydrate(self.__entity_spec.entity_type(), result, from_mssql=True)
        else:
            return None

    def update(self, entity: TEntity) -> None:
        """
        Update an existing record in the table.

        :param entity: The entity with updated values.
        """
        self.__deferred_init()
        entity_data = splat(entity, to_mssql=True)
        primary_key = {
            k: v
            for k, v in entity_data.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        _set = ', '.join([
            f'[{key}] = %?'
            for key in entity_data.keys()
            if key not in self.__entity_spec.primary_key
        ])
        parms = [v for k, v in entity_data.items() if k not in self.__entity_spec.primary_key]
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor.execute(f'UPDATE [{table_name}] SET {_set} WHERE {where}', tuple(parms) + tuple(keys))

    def delete(self, **kwargs: Any) -> None:
        """
        Delete a record from the table using primary key values.

        :param kwargs: Primary key values to filter by.
        """
        self.__deferred_init()
        primary_key = {
            k: self.__to_mssql_value(v)
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
        """
        Check if a record exists in the table using primary key values.

        :param kwargs: Primary key values to filter by.
        :returns: ``True`` if the record exists, otherwise ``False``.
        """
        self.__deferred_init()
        primary_key = {
            k: self.__to_mssql_value(v)
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
        keys = primary_key.values()
        cursor = self.__context.cursor()
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        cursor.execute(f'SELECT TOP 1 1 FROM [{table_name}] WHERE {where}', tuple(keys))
        return cursor.fetchone() is not None

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Insert or update a record in the table.

        If the primary key exists, the record is updated. Otherwise, a new record is inserted.

        :param entity: The entity to upsert.
        :returns: A dictionary containing the primary key values.
        """
        self.__deferred_init()
        entity_data = splat(entity, to_mssql=True)
        pk_value = entity_data.get(self.__entity_spec.primary_key[0], None)
        if self.__entity_spec.has_autoincrement and pk_value in (None, 0):
            return self.create(entity)
        else:
            primary_key = {
                k: v
                for k, v in entity_data.items()
                if k in self.__entity_spec.primary_key
            }
            cols = ', '.join([
                f'[{k}]'
                for k in entity_data.keys()
                if k not in primary_key
            ])
            update = ', '.join([
                f'[{k}]=%?'
                for k in entity_data.keys()
                if k not in primary_key
            ])
            where = ' AND '.join([f'[{k}] = %?' for k in primary_key.keys()])
            cursor = self.__context.cursor()
            table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
            update_parameters = tuple([
                v
                for k, v in entity_data.items()
                if k not in primary_key
            ])
            where_parameters = tuple(primary_key.values())
            if len(where) > 0:
                all_parameters = update_parameters + where_parameters
            else:
                all_parameters = update_parameters
            if len(where) > 0:
                cursor.execute(f'UPDATE [{table_name}] SET {update} WHERE {where}', all_parameters)
            if len(where) == 0 or cursor.rowcount == 0:
                insert_cols = ', '.join([f'[{k}]' for k in entity_data.keys()])
                insert_values = ', '.join(['%?' for _ in entity_data.keys()])
                insert_parameters = tuple(entity_data.values())
                cursor.execute(f'INSERT INTO [{table_name}] ({insert_cols}) VALUES ({insert_values})', insert_parameters)
            return primary_key

    def query(
        self,
        where: str | None = None,
        parameters: DbParameters | None = None,
        orderby: str | None = None,
        limit: int | None = None
    ) -> Generator[TEntity, None, None]:
        """
        Query records from the table with optional filtering and ordering.

        :param where: Optional SQL WHERE clause (without the ``WHERE`` keyword).
        :param parameters: Optional parameters for the WHERE clause.
        :param orderby: Optional SQL ORDER BY clause (without the ``ORDER BY`` keyword).
        :param limit: Optional maximum number of rows to return.
        :yields: Hydrated entity instances.
        """
        self.__deferred_init()
        if parameters is not None:
            parameters = [
                self.__to_mssql_value(p)
                for p in parameters
            ]
        else:
            parameters = []
        where_clause = f' WHERE {where}' if where is not None and len(where) > 0 else ''
        orderby_clause = f' ORDER BY {orderby}' if orderby is not None and len(orderby) > 0 else ''
        top_clause = f' TOP {limit}' if limit is not None and limit > 0 else ''
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        sql = f'SELECT {top_clause}{self.__column_names} FROM [{table_name}]{where_clause}{orderby_clause}'
        cursor = self.__context.cursor()
        cursor.execute(sql, tuple(parameters))
        if cursor.description is None:
            raise DbError('cursor missing required descriptor')
        row = cursor.fetchone()
        while row is not None:
            if cursor.description is None:
                raise DbError('Provider did not provide a description.')
            result = {}
            for kvp in zip(cursor.description, row):
                value = self.__get_pyobject(kvp[0][0], kvp[1])
                if value is not None:
                    result[kvp[0][0]] = value
            yield hydrate(self.__entity_spec.entity_type(), result, from_mssql=True)
            row = cursor.fetchone()


__all__ = ['MSSQLTableAdapter']
