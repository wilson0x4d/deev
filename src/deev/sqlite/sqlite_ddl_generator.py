# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro

from ..entities import EntitySpec, IndexOrder
from .sqlite_type_mapper import SqliteTypeMapper


class SqliteDDLGenerator():
    """
    Generates DDL statements for SQLite tables from entity specifications.

    Produces ``CREATE TABLE IF NOT EXISTS`` statements with column definitions,
    auto-increment for integer PKs, and ``CREATE INDEX`` for secondary indexes.
    """

    def __init__(
        self,
    ) -> None:
        """Initialize the DDL generator."""
        self.__logger = hanaro.get_logger()

    def __generate_table_indexes_ddl(self, entity_spec: EntitySpec, table_name: str) -> list[str]:
        """Build ``CREATE INDEX`` statements for all secondary indexes."""
        ddl = list[str]()
        # Collect fields grouped by their index name.
        groups: dict[str, list[tuple[str, IndexOrder]]] = {}
        for field_name, spec in entity_spec.fields.items():
            if spec.index is None:
                continue
            idx_name = spec.index.name
            direction = spec.index.direction or IndexOrder.ASCENDING
            groups.setdefault(idx_name, []).append((field_name, direction))

        # Map IndexOrder enum to SQL-style ASC/DESC
        direction_map = {IndexOrder.ASCENDING: 'ASC', IndexOrder.DESCENDING: 'DESC'}
        for idx_name, col_specs in sorted(groups.items()):
            # Fields must be alphabetically sorted by field name.
            col_specs.sort(key=lambda cs: cs[0])  # type: ignore
            cols = ', '.join(f'[{name}] {direction_map[direction]}' for name, direction in col_specs)
            ddl.append(f'CREATE INDEX [{idx_name}] ON [{table_name}] ({cols})')
        return ddl

    def generate_table_ddl(
        self,
        *,
        entity_spec: EntitySpec,
        table_name: str | None = None
    ) -> list[str]:
        """
        Generate DDL to create the SQLite table.

        Produces a ``CREATE TABLE`` statement with column definitions,
        primary key constraints, and ``CREATE INDEX`` statements for
        secondary indexes.

        :param entity_spec: The entity specification.
        :param table_name: Optional table name override.
        :return: List of DDL statements including ``CREATE TABLE`` and ``CREATE INDEX``.
        """
        db_type_mapper = SqliteTypeMapper(entity_spec)
        ddl = list[str]()
        table_name = entity_spec.table_name if table_name is None else table_name
        if len(entity_spec.primary_key) == 1:
            # handling a single-column PK
            primary_key = entity_spec.primary_key[0]
            id_dbtype = db_type_mapper.get_provider_type(primary_key)
            columns = ', '.join([
                f'[{k}] {db_type_mapper.get_provider_type(k)}'
                for k in entity_spec.attrs.keys()
                if k != primary_key
            ])
            ddl.append(f'CREATE TABLE IF NOT EXISTS [{table_name}] ({primary_key} {id_dbtype} PRIMARY KEY{" AUTOINCREMENT" if id_dbtype == "INTEGER" else ""}, {columns})')
        else:
            # special handling of multi-column PK
            columns = ', '.join([
                f'[{k}] {db_type_mapper.get_provider_type(k)}'
                for k in entity_spec.attrs.keys()
            ])
            primary_key = (
                f", PRIMARY KEY ({','.join(entity_spec.primary_key)})"
                if len(entity_spec.primary_key) > 0
                else ''
            )
            ddl.append(f'CREATE TABLE IF NOT EXISTS [{table_name}] ({columns}{primary_key})')
        # Generate CREATE INDEX for secondary indexes defined via field(index=...)
        [ddl.append(e) for e in self.__generate_table_indexes_ddl(entity_spec, table_name)]  # type: ignore
        return ddl


__all__ = ['SqliteDDLGenerator']
