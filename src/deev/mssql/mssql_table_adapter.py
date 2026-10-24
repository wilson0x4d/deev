# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any, Callable, Generator, Generic, Sequence, TypeVar, cast, get_args, get_origin
from uuid import UUID

from ..common.db_context import DbContext
from ..common.db_cursor import DbCursor
from ..common.db_error import DbError
from ..common.db_parameters import DbParameters
from ..entities import EntitySpec, apply_defaults_for, construct_entity, get_entity_spec, invoke_on_create_table
from ..translation import compile_hydrate_plan, splat_mssql, to_pyobject
from .mssql_input_sizes import input_sizes, resolve_where_fields
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
    __default_only_names: tuple[str, ...]
    __entity_spec: EntitySpec
    __initialized: bool
    __dbtype_mapper: MSSQLTypeMapper
    __hydrate_plan: tuple[tuple[str, Callable[[Any], Any] | None], ...]
    __table_name: str | None
    __use_setinputsizes: bool

    def __init__(
        self,
        context: DbContext,
        *,
        create_table: bool | None = False,
        table_name: str | None = None,
        use_setinputsizes: bool | None = None
    ) -> None:
        """
        Initialize a new MSSQLTableAdapter.

        :param context: A :class:`DbContext` or :class:`MSSQLProxyConnection` instance.
        :param create_table: Whether to create the table if it does not exist.
        :param table_name: Optional override for the table name.
        :param use_setinputsizes: Whether to internally declare parameter
          type/size information (via ``setinputsizes``) derived from the
          entity/field spec before each parameterized execution.  Defaults
          to ``False``.  Explicit declarations for raw SQL remain available
          at the cursor level via :meth:`MSSQLProxyCursor.setinputsizes`.
        """
        self.__context = context if isinstance(context, (MSSQLProxyConnection, MSSQLTransactionContext)) else MSSQLProxyConnection(context)  # type: ignore[arg-type]
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name
        self.__use_setinputsizes = use_setinputsizes is True

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'[{k}]' for k in self.__entity_spec.fields.keys()])
            self.__hydrate_plan = compile_hydrate_plan(self.__entity_spec, from_mssql=True)
            self.__default_only_names = tuple(name for name, convert in self.__hydrate_plan if convert is None)
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
        try:
            cursor.execute(sql, parameters)
        finally:
            cursor.close()

    def __get_pyobject(self, key: str, value: Any) -> Any:
        """
        Convert a SQL value to the appropriate Python object type.

        :param key: The field name.
        :param value: The raw value from the database.
        :returns: The converted Python object.
        """
        return to_pyobject(
            value,
            cast(type, self.__entity_spec.attrs.get(key)),
            from_mssql=True)

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

    def __apply_input_sizes(self, cursor: DbCursor, field_names: Sequence[str], parameters: Sequence[Any]) -> None:
        """
        Compute and declare parameter type/size information for the next
        execution, in a single step.

        Only acts when ``use_setinputsizes`` is enabled; otherwise the
        driver's native type detection is left undisturbed.  Sizes are
        computed from the entity/field spec (falling back to a default
        inferred from the data type), giving the driver the column's
        correct type/size information — mssql_python sizes string
        parameters from the Python value itself, which fails with "String
        data, right truncation" when a value is longer than the target
        column (even in ``WHERE`` comparisons).

        Explicit declarations for raw SQL remain available at the cursor
        level via :meth:`MSSQLProxyCursor.setinputsizes`.

        :param cursor: The cursor about to execute a parameterized statement.
        :param field_names: The entity field for each parameter, in parameter order.
        :param parameters: The parameter values.
        """
        if self.__use_setinputsizes is not True:
            return
        if len(parameters) == 0:
            return
        sizes = input_sizes(self.__entity_spec, self.__dbtype_mapper, field_names, [tuple(parameters)])
        if sizes is None:
            return
        apply = getattr(cursor, 'setinputsizes', None)
        if apply is not None:
            apply(sizes)

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

    def _do_create_table(self) -> bool:
        """
        Create the target table if it does not already exist.

        :return: ``True`` if the table was created by this call, ``False`` if it already existed.
        """
        self.__deferred_init()
        from .mssql_ddl_generator import MSSQLDDLGenerator
        table_name = self.__entity_spec.table_name if self.__table_name is None else self.__table_name
        # Check if table already exists (SQL Server has no IF NOT EXISTS on CREATE TABLE)
        cursor = self.__context.cursor()
        try:
            cursor.execute(
                'SELECT COUNT(*) FROM sys.tables WHERE name = %?',
                (table_name,)
            )
            result = cursor.fetchone()
        finally:
            cursor.close()
        if result is None or result[0] != 0:
            return False
        ddl_generator = MSSQLDDLGenerator()
        ddl = ddl_generator.generate_table_ddl(entity_spec=self.__entity_spec, table_name=self.__table_name)
        for stmt in ddl:
            self.__execute(stmt)
        return True

    def create_table(self) -> None:
        """
        Create the target table if it does not already exist.

        Generates the table DDL using :class:`MSSQLDDLGenerator` and executes it.
        When the table is created, the entity's ``on_create_table`` hook (if defined) is
        invoked with this adapter.
        """
        created = self._do_create_table()
        if created:
            invoke_on_create_table(self.__entity_spec.entity_type, self)
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
            splat_mssql(entity)
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
        try:
            if self.__entity_spec.has_autoincrement:
                sql = f'INSERT INTO [{table_name}] ({column_names}) OUTPUT INSERTED.[{self.__entity_spec.primary_key[0]}] VALUES ({parms})'
                parameters = tuple(data.values())
                self.__apply_input_sizes(cursor, list(data.keys()), parameters)
                cursor.execute(sql, parameters)
                v = cursor.fetchone()
                if v is not None:
                    pk_values[self.__entity_spec.primary_key[0]] = self.__get_pyobject(self.__entity_spec.primary_key[0], int(v[0]))
                else:
                    raise Exception('Unsupported NULL encountered in primary key.')
            else:
                sql = f'INSERT INTO [{table_name}] ({column_names}) VALUES ({parms})'
                parameters = tuple(data.values())
                self.__apply_input_sizes(cursor, list(data.keys()), parameters)
                cursor.execute(sql, parameters)
            # For non-autoincrement PKs, fetch the inserted row's PK value
            if not pk_values:
                raise DbError('No primary key values provided for non-autoincrement entity.')
            self.__apply_input_sizes(cursor, list(pk_values.keys()), tuple(pk_values.values()))
            cursor.execute(f'SELECT TOP 1 1 FROM [{table_name}] WHERE {" AND ".join([f"[{k}] = ?" for k in pk_values.keys()])}', tuple(pk_values.values()))
            if cursor.fetchone() is None:
                raise DbError('Failed to verify created entity exists.')
        finally:
            cursor.close()
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
        try:
            self.__apply_input_sizes(cursor, list(pk_values.keys()), tuple(keys))
            cursor.execute(sql, tuple(keys))
            data = cursor.fetchone()
            if data:
                return self.__hydrate_row(data)
            else:
                return None
        finally:
            cursor.close()

    def update(self, entity: TEntity) -> None:
        """
        Update an existing record in the table.

        :param entity: The entity with updated values.
        """
        self.__deferred_init()
        entity_data = splat_mssql(entity)
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
        try:
            self.__apply_input_sizes(
                cursor,
                [k for k in entity_data.keys() if k not in self.__entity_spec.primary_key] + list(primary_key.keys()),
                tuple(parms) + tuple(keys)
            )
            cursor.execute(f'UPDATE [{table_name}] SET {_set} WHERE {where}', tuple(parms) + tuple(keys))
        finally:
            cursor.close()

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
        try:
            self.__apply_input_sizes(cursor, list(primary_key.keys()), tuple(keys))
            cursor.execute(sql, tuple(keys))
        finally:
            cursor.close()

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
        try:
            self.__apply_input_sizes(cursor, list(primary_key.keys()), tuple(keys))
            cursor.execute(f'SELECT TOP 1 1 FROM [{table_name}] WHERE {where}', tuple(keys))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        """
        Insert or update a record in the table.

        If the primary key exists, the record is updated. Otherwise, a new record is inserted.

        :param entity: The entity to upsert.
        :returns: A dictionary containing the primary key values.
        """
        self.__deferred_init()
        entity_data = splat_mssql(entity)
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
            try:
                if len(where) > 0:
                    self.__apply_input_sizes(
                        cursor,
                        [k for k in entity_data.keys() if k not in primary_key] + list(primary_key.keys()),
                        all_parameters
                    )
                    cursor.execute(f'UPDATE [{table_name}] SET {update} WHERE {where}', all_parameters)
                if len(where) == 0 or cursor.rowcount == 0:
                    insert_cols = ', '.join([f'[{k}]' for k in entity_data.keys()])
                    insert_values = ', '.join(['%?' for _ in entity_data.keys()])
                    insert_parameters = tuple(entity_data.values())
                    self.__apply_input_sizes(cursor, list(entity_data.keys()), insert_parameters)
                    cursor.execute(f'INSERT INTO [{table_name}] ({insert_cols}) VALUES ({insert_values})', insert_parameters)
            finally:
                cursor.close()
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
        try:
            if where is not None and len(parameters) > 0:
                resolved = resolve_where_fields(where, list(self.__entity_spec.fields.keys()))
                if len(resolved) == len(parameters) and all(f is not None for f in resolved):
                    self.__apply_input_sizes(cursor, [f for f in resolved if f is not None], tuple(parameters))
            cursor.execute(sql, tuple(parameters))
            row = cursor.fetchone()
            while row is not None:
                yield self.__hydrate_row(row)
                row = cursor.fetchone()
        finally:
            cursor.close()


__all__ = ['MSSQLTableAdapter']
