# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from punit import fact, inlinedata, theory
from deev.clickhouse.utils import resolve_clickhouse_table_engine


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
