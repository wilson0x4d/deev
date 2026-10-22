# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev import entity, field
from deev.clickhouse import ClickHouseDDLGenerator
from deev.clickhouse.utils import resolve_clickhouse_table_engine
from deev.entities import IndexOptions, get_entity_spec
from punit import fact, inlinedata, theory
from uuid import UUID


@theory
@inlinedata('ReplicatedMergeTree', 'ReplicatedMergeTree')
@inlinedata("ReplicatedMergeTree('/clickhouse/databases/{database}', '{shard}', '{replica}')", "ReplicatedMergeTree('/clickhouse/databases/{database}', '{shard}', '{replica}')")
@inlinedata('Atomic', 'MergeTree')
@inlinedata('Lazy', 'MergeTree')
@inlinedata('Memory', 'MergeTree')
@inlinedata('Shared', 'MergeTree')
@inlinedata('MergeTree', 'MergeTree')
@inlinedata('MergeTree()', 'MergeTree()')
@inlinedata('SomeEngine', 'MergeTree')
@inlinedata("SomeEngine('param')", "MergeTree('param')")
def resolves_clickhouse_table_engine(db_engine_full: str, expected: str) -> None:
    result = resolve_clickhouse_table_engine(db_engine_full)
    assert result == expected


@fact
def clickhouse_ddl_field_in_multiple_skip_indexes() -> None:
    @entity
    class ChMultiSkipEntity:
        id: UUID = field(primary_key=True)
        payload: str = field(index=[
            IndexOptions(name='ch_ix_minmax', type='minmax'),
            IndexOptions(name='ch_ix_bloom', type='bloom_filter'),
        ])
    ddl = ClickHouseDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(ChMultiSkipEntity))
    create = next(s for s in ddl if s.startswith('CREATE TABLE'))
    assert 'INDEX `ch_ix_minmax` payload TYPE minmax' in create, f'minmax skip index missing: {create}'
    assert 'INDEX `ch_ix_bloom` payload TYPE bloom_filter' in create, f'bloom_filter skip index missing: {create}'
