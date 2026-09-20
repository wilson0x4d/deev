# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro
import logging

from ..entities import EntitySpec, IndexOrder
from .mssql_type_mapper import MSSQLTypeMapper


class MSSQLDDLGenerator:
    """
    Generates Data Definition Language (DDL) statements for Microsoft SQL Server.
    """

    __logger: logging.Logger

    def __init__(
        self,
    ) -> None:
        self.__logger = hanaro.get_logger()

    def __generate_table_indexes_ddl(self, entity_spec: EntitySpec, table_name: str) -> list[str]:
        """
        Build ``CREATE INDEX`` statements for all secondary indexes.

        :param entity_spec: The entity specification containing index metadata.
        :param table_name: The target table name.
        :returns: A list of ``CREATE INDEX`` SQL statements.
        """
        ddl = list[str]()
        direction_map = {IndexOrder.ASCENDING: 'ASC', IndexOrder.DESCENDING: 'DESC'}
        groups: dict[str, list[tuple[str, IndexOrder]]] = {}
        for field_name, spec in entity_spec.fields.items():
            if spec.index is None:
                continue
            idx_name = spec.index.name
            direction = spec.index.direction or IndexOrder.ASCENDING
            groups.setdefault(idx_name, []).append((field_name, direction))

        for idx_name, col_specs in sorted(groups.items()):
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
        Generate DDL statements to create the table and its indexes.

        :param entity_spec: The entity specification describing the table structure.
        :param table_name: Optional override for the table name.
        :returns: A list of DDL SQL statements.
        """
        db_type_mapper = MSSQLTypeMapper(entity_spec)
        ddl = list[str]()
        table_name = entity_spec.table_name if table_name is None else table_name
        if len(entity_spec.primary_key) == 1:
            primary_key = entity_spec.primary_key[0]
            id_dbtype = db_type_mapper.get_provider_type(primary_key)
            columns = ', '.join([
                f'[{k}] {db_type_mapper.get_provider_type(k)}'
                for k in entity_spec.attrs.keys()
                if k != primary_key
            ])
            auto_increment = f' IDENTITY(1,1)' if id_dbtype in ('INT', 'BIGINT', 'SMALLINT') else ''
            ddl.append(f'CREATE TABLE [{table_name}] ({primary_key} {id_dbtype}{auto_increment}, {columns}, PRIMARY KEY ({primary_key}))')
        else:
            columns = ', '.join([
                f'[{k}] {db_type_mapper.get_provider_type(k)}'
                for k in entity_spec.attrs.keys()
            ])
            primary_key = (
                f", PRIMARY KEY ({','.join(entity_spec.primary_key)})"
                if len(entity_spec.primary_key) > 0
                else ''
            )
            ddl.append(f'CREATE TABLE [{table_name}] ({columns}{primary_key})')
        for e in self.__generate_table_indexes_ddl(entity_spec, table_name):
            ddl.append(e)
        return ddl


__all__ = ['MSSQLDDLGenerator']
