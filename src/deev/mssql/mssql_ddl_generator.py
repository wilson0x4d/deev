# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging

from ..entities import EntitySpec, IndexOrder, get_entity_spec
from .mssql_type_mapper import MSSQLTypeMapper


class MSSQLDDLGenerator:
    """
    Generates Data Definition Language (DDL) statements for Microsoft SQL Server.

    Produces ``CREATE TABLE`` statements with column definitions, primary key
    constraints, ``FOREIGN KEY`` constraints for foreign-key fields, and
    ``CREATE INDEX`` statements for secondary indexes.
    """

    __logger: logging.Logger

    def __init__(
        self,
    ) -> None:
        self.__logger = hanaro.get_logger()

    def __generate_foreign_keys_ddl(self, entity_spec: EntitySpec) -> list[str]:
        """
        Build ``FOREIGN KEY`` table constraints for all foreign-key fields.

        :param entity_spec: The entity specification containing foreign-key metadata.
        :returns: A list of ``FOREIGN KEY`` SQL constraint fragments.
        """
        fks = list[str]()
        for field_name, spec in entity_spec.fields.items():
            if spec.foreign_key is None:
                continue
            target_entity_type, target_field = spec.foreign_key
            target_table_name = get_entity_spec(target_entity_type).table_name
            cascade = ' ON DELETE CASCADE' if spec.cascade_delete is True else ''
            fks.append(f'FOREIGN KEY ([{field_name}]) REFERENCES [{target_table_name}]([{target_field}]){cascade}')
        return fks

    def __generate_table_indexes_ddl(self, entity_spec: EntitySpec, table_name: str) -> list[str]:
        """
        Build ``CREATE INDEX`` statements for all secondary indexes.

        :param entity_spec: The entity specification containing index metadata.
        :param table_name: The target table name.
        :returns: A list of ``CREATE INDEX`` SQL statements.
        """
        ddl = list[str]()
        direction_map = {IndexOrder.ASCENDING: 'ASC', IndexOrder.DESCENDING: 'DESC'}
        groups: dict[str, list[tuple[str, IndexOrder, int]]] = {}
        for field_name, spec in entity_spec.fields.items():
            for idx_opts in spec.indexes:
                direction = idx_opts.direction or IndexOrder.ASCENDING
                groups.setdefault(idx_opts.name, []).append((field_name, direction, idx_opts.rank))

        for idx_name, col_specs in sorted(groups.items()):
            # fields are ordered by rank, ties broken alphabetically by field name.
            col_specs.sort(key=lambda cs: (cs[2], cs[0]))  # type: ignore
            cols = ', '.join(f'[{name}] {direction_map[direction]}' for name, direction, _ in col_specs)
            ddl.append(f'CREATE INDEX [{idx_name}] ON [{table_name}] ({cols})')
        return ddl

    def generate_table_ddl(
        self,
        *,
        entity_spec: EntitySpec,
        table_name: str | None = None
    ) -> list[str]:
        """
        Generate DDL statements to create the table and its indexes.

        :param entity_spec: The entity specification describing the table structure.
        :param table_name: Optional override for the table name.
        :returns: A list of DDL SQL statements.
        """
        db_type_mapper = MSSQLTypeMapper(entity_spec)
        ddl = list[str]()
        table_name = entity_spec.table_name if table_name is None else table_name
        definitions = list[str]()
        if len(entity_spec.primary_key) == 1:
            primary_key = entity_spec.primary_key[0]
            id_dbtype = db_type_mapper.get_provider_type(primary_key)
            auto_increment = f' IDENTITY(1,1)' if id_dbtype in ('INT', 'BIGINT', 'SMALLINT') else ''
            definitions.append(f'{primary_key} {id_dbtype}{auto_increment}')
            definitions.extend([
                f'[{k}] {db_type_mapper.get_provider_type(k)}'
                for k in entity_spec.attrs.keys()
                if k != primary_key
            ])
            definitions.append(f'PRIMARY KEY ({primary_key})')
        else:
            definitions.extend([
                f'[{k}] {db_type_mapper.get_provider_type(k)}'
                for k in entity_spec.attrs.keys()
            ])
            if len(entity_spec.primary_key) > 0:
                definitions.append(f'PRIMARY KEY ({", ".join(entity_spec.primary_key)})')
        definitions.extend(self.__generate_foreign_keys_ddl(entity_spec))
        ddl.append(f'CREATE TABLE [{table_name}] ({", ".join(definitions)})')
        for e in self.__generate_table_indexes_ddl(entity_spec, table_name):
            ddl.append(e)
        return ddl


__all__ = ['MSSQLDDLGenerator']
