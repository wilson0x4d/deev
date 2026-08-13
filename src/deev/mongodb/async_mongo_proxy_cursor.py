# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import re
from typing import (
    Any,
    Sequence
)
import hanaro
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection

from ..common.async_db_cursor import AsyncDbCursor
from ..common.db_error import DbError
from ..common.db_params import DbParams
from .utils import infer_description_fields, parse_sql_where


class AsyncMongoProxyCursor:
    """
    Async DB-API 2.0 compliant cursor interface for MongoDB.
    Translates SQL-like statements to native MongoDB operations via the
    underlying AsyncClientSession and returns documents as dicts/tuples.
    """
    __database_name: str
    __result_set: list[dict[str, Any]] | None
    __logger: logging.Logger
    __row_count: int
    __row_index: int
    __session: AsyncClientSession
    __sql_arg_expect: str
    __description_fields: tuple[str, ...] | None
    __last_collection: AsyncCollection | None

    def __init__(self, provider_session: AsyncClientSession, database_name: str) -> None:
        self.__session = provider_session
        self.__database_name = database_name
        self.__sql_arg_expect = '%?'
        self.__description_fields = None
        self.__logger = hanaro.get_logger()
        self.__last_collection = None
        self.__result_set = None
        self.__row_index = 0
        self.__row_count = 0

    @property
    def description(self) -> Sequence[tuple[Any, Any, int | None, int | None, int | None, int | None, bool]] | None:
        if self.__result_set is not None and len(self.__result_set) > 0:
            first_doc = self.__result_set[0]
            fields = list(self.__description_fields) if self.__description_fields else list(first_doc.keys())
            return tuple(
                (
                    name,
                    *self._describe_field(name, first_doc),
                    True,
                )
                for name in fields
            )
        return None

    def _describe_field(self, field_name: str, doc: dict[str, Any]) -> tuple[Any, int | None, int | None, int | None, int | None]:
        """Infer DB-API 2.0 description fields from a single document's value."""
        value = doc.get(field_name)
        return infer_description_fields(value)

    @property
    def rowcount(self) -> int:
        return self.__row_count

    @property
    def mongo_session(self) -> AsyncClientSession:
        return self.__session

    def __get_database(self):
        """Return the async pymongo database from the session's client."""
        return self.__session._client[self.__database_name]  # type: ignore[attr-defined]

    def _get_collection(self) -> AsyncCollection:
        """Return the collection from the session's database."""
        db = self.__get_database()
        return db['deev']  # type: ignore[return-value]

    def _set_collection_name(self, name: str) -> None:
        """Store the target collection name for use by mongo_fetch* methods."""
        self.__last_collection = self.__get_database()[name]  # type: ignore[attr-defined]

    async def execute(self, operation: str, params: DbParams | None = None) -> None:
        param_tuple: tuple[Any, ...] = tuple(params) if params is not None else ()
        operation_upper = operation.strip().upper()
        self.__row_index = 0
        self.__result_set = None
        self.__description_fields = None
        try:
            if operation_upper.startswith('SELECT'):
                await self._execute_select(operation, param_tuple)
            elif operation_upper.startswith('INSERT'):
                await self._execute_insert(operation, param_tuple)
            elif operation_upper.startswith('UPDATE'):
                await self._execute_update(operation, param_tuple)
            elif operation_upper.startswith('DELETE'):
                await self._execute_delete(operation, param_tuple)
            else:
                pass
        except Exception as exc:
            self.__logger.error('AsyncMongoProxyCursor.execute failed: %s', str(exc))
            raise DbError(f'MongoDB operation failed: {exc}') from exc

    async def _execute_select(self, sql: str, params: tuple[Any, ...]) -> None:
        """Parse a SELECT statement and execute the corresponding MongoDB find."""
        select_re = re.compile(
            r"SELECT\s+(.+?)(?:\s+FROM\s+(`[^`]+`|\w+))?(?:\s+WHERE\s+(.+?))?(?:\s+ORDER\s+BY\s+(.+?))?(?:\s+LIMIT\s+(\d+))?\s*$",
            re.IGNORECASE | re.DOTALL,
        )
        m = select_re.match(sql.strip())
        if not m:
            raise DbError(f'Cannot parse SELECT statement: {sql}')
        columns_str = m.group(1).strip()
        table_name = m.group(2)
        col_names = [c.strip().strip('`][]"') for c in columns_str.split(',')]
        if table_name is None:
            # SELECT without FROM (e.g. `SELECT 1`) — valid no-op for migration scripts;
            # produce an empty result set whose description matches the selected columns.
            self.__result_set = []
            self.__description_fields = tuple(col_names)
            self.__row_count = 0
            return
        else:
            table_name.strip('`]["')
        where_clause = m.group(3)
        order_by_str = m.group(4)
        limit_val = int(m.group(5)) if m.group(5) else None
        self._set_collection_name(table_name)
        if columns_str == '*':
            projection: dict[str, int] | None = None
            col_names.clear()
            doc_sample = await self.__get_database()[table_name].find_one({})
            if doc_sample is not None:
                col_names = [k for k in doc_sample.keys() if k != '_id']
        else:
            col_names = [c.strip().strip('`]["') for c in columns_str.split(',')]
            projection = {c: 1 for c in col_names}
        where_filter = parse_sql_where(where_clause, params) if where_clause else {}
        sort_spec: list[tuple[str, int]] | None = None
        if order_by_str:
            sort_entries = [s.strip() for s in order_by_str.split(',')]
            sort_spec = []
            for entry in sort_entries:
                parts = entry.rsplit(None, 1)
                field = parts[0].strip().strip('`').strip('"')
                direction = parts[1].upper() if len(parts) > 1 else 'ASC'
                sort_spec.append((field, -1 if direction == 'DESC' else 1))
        cursor = self.__get_database()[table_name].find(where_filter, projection=projection)
        if sort_spec:
            cursor = cursor.sort(sort_spec)
        if limit_val is not None:
            cursor = cursor.limit(limit_val)
        docs = []
        async for doc in cursor:
            docs.append(doc)
        if docs:
            self.__result_set = docs
            self.__description_fields = tuple(col_names)
        else:
            self.__result_set = []
            self.__description_fields = tuple(col_names)
        self.__row_count = len(docs)

    async def _execute_insert(self, sql: str, params: tuple[Any, ...]) -> None:
        """Parse an INSERT statement and execute the corresponding MongoDB insert_one."""
        insert_re = re.compile(
            r'INSERT\s+(?:\w+\s+)?(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*$',
            re.IGNORECASE | re.DOTALL,
        )
        m = insert_re.match(sql.strip())
        if not m:
            raise DbError(f'Cannot parse INSERT statement: {sql}')
        table_name = m.group(1)
        if table_name is None:
            raise DbError('INSERT without a table name present not supported for MongoDB')
        else:
            table_name.strip('`]["')
        columns_str = m.group(2)
        values_str = m.group(3)
        self._set_collection_name(table_name)
        columns = [c.strip().strip('`').strip('"') for c in columns_str.split(',')]
        value_strings = [v.strip() for v in values_str.split(',')]
        values: list[Any] = []
        param_idx = 0
        for vs in value_strings:
            if vs == '%?':
                if param_idx < len(params):
                    values.append(params[param_idx])
                    param_idx += 1
                else:
                    raise DbError('INSERT statement has more placeholders than provided parameters.')
            elif vs.startswith("'") and vs.endswith("'"):
                values.append(vs[1:-1])
            elif vs == 'NULL':
                values.append(None)
            else:
                try:
                    if '.' in vs:
                        values.append(float(vs))
                    else:
                        values.append(int(vs))
                except ValueError:
                    raise DbError(f'Cannot parse value literal in INSERT: {vs}')
        doc = dict(zip(columns, values))
        await self.__get_database()[table_name].insert_one(doc)
        self.__result_set = [doc]
        self.__description_fields = tuple(doc.keys())
        self.__row_count = 1

    async def _execute_update(self, sql: str, params: tuple[Any, ...]) -> None:
        """Parse an UPDATE statement and execute the corresponding MongoDB update_one."""
        update_re = re.compile(
            r'UPDATE\s+(\w+)\s+SET\s+(.+?)\s+WHERE\s+(.+)\s*$',
            re.IGNORECASE | re.DOTALL,
        )
        m = update_re.match(sql.strip())
        if not m:
            raise DbError(f'Cannot parse UPDATE statement: {sql}')
        table_name = m.group(1)
        if table_name is None:
            raise DbError('UPDATE without a table name present not supported for MongoDB')
        else:
            table_name.strip('`]["')
        set_clause = m.group(2).strip()
        where_clause = m.group(3).strip()
        self._set_collection_name(table_name)
        assignments_re = re.compile(r"(\w+)\s*=\s*(\%\?|'[^']*'|NULL|\d+(?:\.\d+)?)")
        assignment_pairs = assignments_re.findall(set_clause)
        where_filter = parse_sql_where(where_clause, params) if where_clause else {}
        update_data: dict[str, Any] = {}
        param_idx = 0
        for field_name, value_str in assignment_pairs:
            if value_str == '%?':
                if param_idx < len(params):
                    update_data[field_name] = params[param_idx]
                    param_idx += 1
                else:
                    raise DbError('UPDATE statement has more SET placeholders than provided parameters.')
            elif value_str.startswith("'") and value_str.endswith("'"):
                update_data[field_name] = value_str[1:-1]
            elif value_str == 'NULL':
                update_data[field_name] = None
            else:
                try:
                    if '.' in value_str:
                        update_data[field_name] = float(value_str)
                    else:
                        update_data[field_name] = int(value_str)
                except ValueError:
                    raise DbError(f'Cannot parse SET literal: {value_str}')
        match_result = await self.__get_database()[table_name].update_one(where_filter, {'$set': update_data})
        self.__row_count = match_result.modified_count

    async def _execute_delete(self, sql: str, params: tuple[Any, ...]) -> None:
        """Parse a DELETE statement and execute the corresponding MongoDB delete_one."""
        delete_re = re.compile(
            r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+))?\s*$',
            re.IGNORECASE | re.DOTALL,
        )
        m = delete_re.match(sql.strip())
        if not m:
            raise DbError(f'Cannot parse DELETE statement: {sql}')
        table_name = m.group(1)
        if table_name is None:
            raise DbError('DELETE without a table name present not supported for MongoDB')
        else:
            table_name.strip('`]["')
        where_clause = m.group(2)
        self._set_collection_name(table_name)
        where_filter = parse_sql_where(where_clause, params) if where_clause else {}
        match_result = await self.__get_database()[table_name].delete_one(where_filter)
        self.__row_count = match_result.deleted_count

    async def executemany(self, operation: str, seq_params: Sequence[DbParams]) -> None:
        """Execute an INSERT with multiple parameter sets."""
        insert_re = re.compile(
            r'INSERT\s+(?:\w+\s+)?(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*$',
            re.IGNORECASE | re.DOTALL,
        )
        m = insert_re.match(operation.strip())
        if not m:
            await self.execute(operation, seq_params[0] if seq_params else None)
            return
        table_name = m.group(1)
        columns_str = m.group(2)
        values_pattern = m.group(3)
        columns = [c.strip().strip('`]["') for c in columns_str.split(',')]
        placeholders = values_pattern.split(',')
        docs: list[dict[str, Any]] = []
        for param_set in seq_params:
            param_tuple = tuple(param_set) if not isinstance(param_set, tuple) else param_set
            doc: dict[str, Any] = {}
            pi = 0
            for ph in placeholders:
                ph = ph.strip()
                if ph == '%?':
                    if pi < len(param_tuple):
                        doc[columns[pi]] = param_tuple[pi]
                        pi += 1
                    else:
                        raise DbError('executemany parameter count mismatch.')
                elif ph.startswith("'") and ph.endswith("'"):
                    doc[columns[pi]] = ph[1:-1]
                    pi += 1
                else:
                    try:
                        if '.' in ph:
                            doc[columns[pi]] = float(ph)
                        else:
                            doc[columns[pi]] = int(ph)
                    except ValueError:
                        raise DbError(f'Cannot parse value literal: {ph}')
            docs.append(doc)
        self._set_collection_name(table_name)
        if docs:
            result = await self.__get_database()[table_name].insert_many(docs)
            self.__result_set = docs
            self.__description_fields = tuple(columns)
            self.__row_count = len(result.inserted_ids)
        else:
            self.__result_set = []
            self.__row_count = 0

    async def fetchone(self) -> tuple[Any, ...] | None:
        doc = self.mongo_fetchone()
        if doc is None:
            return None
        return tuple(doc.values())

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        docs = self.mongo_fetchmany(size)
        return [tuple(d.values()) for d in docs]

    async def fetchall(self) -> list[tuple[Any, ...]]:
        docs = self.mongo_fetchall()
        return [tuple(d.values()) for d in docs]

    def mongo_fetchone(self) -> dict[str, Any] | None:
        if self.__result_set is None or self.__row_index >= len(self.__result_set):
            return None
        doc = self.__result_set[self.__row_index]
        self.__row_index += 1
        return dict(doc)

    def mongo_fetchmany(self, size: int = 1) -> list[dict[str, Any]]:
        if self.__result_set is None or self.__row_index >= len(self.__result_set):
            return []
        remaining = len(self.__result_set) - self.__row_index
        count = min(size, remaining)
        docs = self.__result_set[self.__row_index:self.__row_index + count]
        self.__row_index += count
        return [dict(d) for d in docs]

    def mongo_fetchall(self) -> list[dict[str, Any]]:
        if self.__result_set is None or self.__row_index >= len(self.__result_set):
            return []
        docs = self.__result_set[self.__row_index:]
        self.__row_index = len(self.__result_set)
        return [dict(d) for d in docs]

    async def close(self) -> None:
        """End the underlying pymongo session to release server-side resources."""
        try:
            await self.__session.end_session()
        except Exception:
            # end_session may raise if already ended; ignore for graceful cleanup
            pass


__all__ = ['AsyncMongoProxyCursor']
