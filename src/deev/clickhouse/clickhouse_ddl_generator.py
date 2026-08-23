# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hanaro

from ..entities import EntitySpec, IndexOptions
from .clickhouse_type_mapper import ClickHouseTypeMapper
from .utils import CLICKHOUSE_SKIP_INDEX_TYPES


class ClickHouseDDLGenerator():

    def __init__(
        self,
    ) -> None:
        self.__logger = hanaro.get_logger()

    def generate_table_ddl(
        self,
        *,
        entity_spec: EntitySpec,
        table_name: str | None = None,
        engine: str | None = None,
        order_by: str | None = None,
        partition_by: str | None = None
    ) -> list[str]:
        """Generate DDL to create the table."""
        #
        ddl = list[str]()
        db_type_mapper = ClickHouseTypeMapper(entity_spec)
        table_name = entity_spec.table_name if table_name is None else table_name
        primary_key = entity_spec.primary_key
        columns = ', '.join([
            f'`{k}` {db_type_mapper.get_provider_type(k)}'
            for k in entity_spec.attrs.keys()
        ])
        skip_indexes: list[str] = []
        seen_index_names: set[str] = set()
        for field_name, field_spec in entity_spec.fields.items():
            idx_opts: IndexOptions | None = field_spec.index
            if idx_opts is None:
                continue
            if idx_opts.type is None or idx_opts.type not in CLICKHOUSE_SKIP_INDEX_TYPES:
                self.__logger.warning(
                    f'Field `{field_name}` has index `{idx_opts.name}` but type is {"not set" if idx_opts.type is None else f"unrecognized: `{idx_opts.type}`"}' +
                    f'. Allowed skip index types: {", ".join(sorted(CLICKHOUSE_SKIP_INDEX_TYPES))}'
                )
                continue
            if idx_opts.name in seen_index_names:
                continue
            seen_index_names.add(idx_opts.name)
            skip_indexes.append(
                f'INDEX `{idx_opts.name}` {field_name} TYPE {idx_opts.type}'
            )

        all_definitions = columns
        if skip_indexes:
            all_definitions = columns + ', ' + ', '.join(skip_indexes)

        if engine is None:
            engine = 'ReplicatedMergeTree()'

        if order_by:
            order_clause = f' ORDER BY ({order_by})'
        else:
            order_columns: list[str] = [f'`{k}`' for k in primary_key]

            if order_columns:
                order_clause = f' ORDER BY ({", ".join(order_columns)})'
            else:
                order_clause = ''

        partition_clause = f' PARTITION BY ({partition_by})' if partition_by else ''

        ddl.append(f'CREATE TABLE IF NOT EXISTS `{table_name}` ({all_definitions}) ENGINE = {engine}{order_clause}{partition_clause}')
        return ddl


__all__ = ['ClickHouseDDLGenerator']
