# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

CLICKHOUSE_SKIP_INDEX_TYPES: frozenset[str] = frozenset({
    'minmax',
    'set',
    'bloom_filter',
    'tokenbf_v1',
    'ngrambf_v1',
    'text',
})


__all__ = [
    'CLICKHOUSE_SKIP_INDEX_TYPES'
]
