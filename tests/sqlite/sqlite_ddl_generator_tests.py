# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import sqlite3
from deev import entity, field
from deev.entities import get_entity_spec, IndexOptions
from deev.sqlite import SQLiteDDLGenerator
from punit import fact, trait
from uuid import UUID, uuid4


@entity
class FKParent:
    id: int = field(primary_key=True, autoincrement=True)


@entity
class FKChild:
    id: int = field(primary_key=True, autoincrement=True)
    parent_id: int = field(foreign_key=(FKParent, 'id'))


@entity
class FKChildCascade:
    id: int = field(primary_key=True, autoincrement=True)
    parent_id: int = field(foreign_key=(FKParent, 'id'), cascade_delete=True)


@entity
class FKNoConstraint:
    id: int = field(primary_key=True, autoincrement=True)
    plain: int


def _create_table_ddl(entity_type: type) -> str:
    ddl = SQLiteDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(entity_type))
    return next(s for s in ddl if s.startswith('CREATE TABLE'))


def _create_index_ddl(entity_type: type, index_name: str) -> str:
    ddl = SQLiteDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(entity_type))
    return next(s for s in ddl if s.startswith(f'CREATE INDEX [{index_name}]'))


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_emits_foreign_key_constraint() -> None:
    ddl = _create_table_ddl(FKChild)
    assert 'FOREIGN KEY ([parent_id]) REFERENCES [FKParents]([id])' in ddl, f'FK clause missing: {ddl}'


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_emits_cascade_delete_when_configured() -> None:
    ddl = _create_table_ddl(FKChildCascade)
    assert 'FOREIGN KEY ([parent_id]) REFERENCES [FKParents]([id]) ON DELETE CASCADE' in ddl, f'cascade FK clause missing: {ddl}'


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_omits_foreign_key_when_not_configured() -> None:
    ddl = _create_table_ddl(FKNoConstraint)
    assert 'FOREIGN KEY' not in ddl, f'unexpected FK clause: {ddl}'
    assert 'ON DELETE CASCADE' not in ddl, f'unexpected cascade clause: {ddl}'


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_single_column_table_has_no_trailing_comma() -> None:
    # a table whose only column is its PK must still produce valid DDL
    @entity
    class SoloId:
        id: UUID = field(primary_key=True)
    ddl = _create_table_ddl(SoloId)
    assert ', )' not in ddl, f'trailing comma present: {ddl}'
    assert ddl == 'CREATE TABLE IF NOT EXISTS [SoloIds] (id TEXT PRIMARY KEY)', f'unexpected ddl: {ddl}'


@fact
@trait('integration', 'sqlite')
def sqlite_fk_cascade_delete_enforced() -> None:
    gen = SQLiteDDLGenerator()
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        parent_table = get_entity_spec(FKParent).table_name
        child_table = get_entity_spec(FKChildCascade).table_name
        for entity_type in (FKParent, FKChildCascade):
            for stmt in gen.generate_table_ddl(entity_spec=get_entity_spec(entity_type)):
                conn.execute(stmt)
        parent_id = conn.execute(f'INSERT INTO [{parent_table}] DEFAULT VALUES').lastrowid
        assert parent_id is not None, 'expected a parent rowid.'
        conn.execute(f'INSERT INTO [{child_table}] (id, parent_id) VALUES (?, ?)', (1, parent_id))
        assert conn.execute(f'SELECT COUNT(*) FROM [{child_table}]').fetchone()[0] == 1, 'child not created.'
        conn.execute(f'DELETE FROM [{parent_table}] WHERE id = ?', (parent_id,))
        assert conn.execute(f'SELECT COUNT(*) FROM [{child_table}]').fetchone()[0] == 0, 'cascade delete did not remove child.'
    finally:
        conn.close()


@fact
@trait('integration', 'sqlite')
def sqlite_fk_without_cascade_preserves_child() -> None:
    gen = SQLiteDDLGenerator()
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        parent_table = get_entity_spec(FKParent).table_name
        child_table = get_entity_spec(FKChild).table_name
        for entity_type in (FKParent, FKChild):
            for stmt in gen.generate_table_ddl(entity_spec=get_entity_spec(entity_type)):
                conn.execute(stmt)
        parent_id = conn.execute(f'INSERT INTO [{parent_table}] DEFAULT VALUES').lastrowid
        assert parent_id is not None, 'expected a parent rowid.'
        conn.execute(f'INSERT INTO [{child_table}] (id, parent_id) VALUES (?, ?)', (1, parent_id))
        assert conn.execute(f'SELECT COUNT(*) FROM [{child_table}]').fetchone()[0] == 1, 'child not created.'
        # deleting the parent must be rejected by the FK constraint (no cascade)
        try:
            conn.execute(f'DELETE FROM [{parent_table}] WHERE id = ?', (parent_id,))
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError('expected FK constraint to block parent delete.')
    finally:
        conn.close()


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_composite_index_fields_ordered_by_rank() -> None:
    @entity
    class RankOrderedEntity:
        id: int = field(primary_key=True, autoincrement=True)
        zebra: str = field(index=IndexOptions(name='ix_rank_ordered', rank=0))
        apple: str = field(index=IndexOptions(name='ix_rank_ordered', rank=1))
    ddl = _create_index_ddl(RankOrderedEntity, 'ix_rank_ordered')
    expected = 'CREATE INDEX [ix_rank_ordered] ON [RankOrderedEntities] ([zebra] ASC, [apple] ASC)'
    assert ddl == expected, f'(expected={expected}, actual={ddl})'


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_composite_index_equal_ranks_sorted_alphabetically() -> None:
    @entity
    class EqualRankEntity:
        id: int = field(primary_key=True, autoincrement=True)
        last_name: str = field(index=IndexOptions(name='ix_equal_rank', rank=1))
        first_name: str = field(index=IndexOptions(name='ix_equal_rank', rank=1))
    ddl = _create_index_ddl(EqualRankEntity, 'ix_equal_rank')
    expected = 'CREATE INDEX [ix_equal_rank] ON [EqualRankEntities] ([first_name] ASC, [last_name] ASC)'
    assert ddl == expected, f'(expected={expected}, actual={ddl})'


@fact
@trait('unit', 'sqlite')
def sqlite_ddl_field_in_multiple_indexes() -> None:
    @entity
    class MultiIndexEntity:
        id: int = field(primary_key=True, autoincrement=True)
        status: str = field(index=[IndexOptions(name='ix_status_created', rank=0), 'ix_status_only'])
        created: str = field(index=IndexOptions(name='ix_status_created', rank=1))
    expected_a = 'CREATE INDEX [ix_status_created] ON [MultiIndexEntities] ([status] ASC, [created] ASC)'
    assert _create_index_ddl(MultiIndexEntity, 'ix_status_created') == expected_a, f'missing or malformed {expected_a}'
    expected_b = 'CREATE INDEX [ix_status_only] ON [MultiIndexEntities] ([status] ASC)'
    assert _create_index_ddl(MultiIndexEntity, 'ix_status_only') == expected_b, f'missing or malformed {expected_b}'
