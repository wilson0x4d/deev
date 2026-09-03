# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

"""ClickHouse utility constants and helpers."""

CLICKHOUSE_SKIP_INDEX_TYPES: frozenset[str] = frozenset({
    'minmax',
    'set',
    'bloom_filter',
    'tokenbf_v1',
    'ngrambf_v1',
    'text',
})


def resolve_clickhouse_table_engine(db_engine_full: str) -> str:
    """
    Derive a ClickHouse table engine spec from a database's engine_full spec.
    
    'Replicated(...)' → 'ReplicatedMergeTree(...)' (preserves parens/content)
    'Atomic'          → 'MergeTree'
    'Lazy'            → 'MergeTree'
    'Memory'          → 'MergeTree'
    'Shared'          → 'MergeTree'
    'Unknown'         → 'MergeTree'
    """
    if '(' in db_engine_full:
        idx = db_engine_full.index('(')
        base = db_engine_full[:idx].strip()
        params = db_engine_full[idx:]
    else:
        base = db_engine_full.strip()
        params = ''
    
    mapping = {
        'Replicated': 'ReplicatedMergeTree',
        'ReplicatedMergeTree': 'ReplicatedMergeTree',
        'Atomic': 'MergeTree',
        'Lazy': 'MergeTree',
        'Memory': 'MergeTree',
        'Shared': 'MergeTree',
    }
    table_base = mapping.get(base, 'MergeTree')
    return f'{table_base}{params}'


__all__ = [
    'CLICKHOUSE_SKIP_INDEX_TYPES',
    'resolve_clickhouse_table_engine',
]
