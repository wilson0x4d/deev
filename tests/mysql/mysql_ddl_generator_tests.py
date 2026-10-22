# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev import entity, field
from deev.entities import get_entity_spec, IndexOptions
from deev.mysql import MySQLDDLGenerator
from punit import fact, trait
from uuid import UUID


@entity
class MyFKParent:
    id: UUID = field(primary_key=True)


@entity
class MyFKChild:
    id: UUID = field(primary_key=True)
    parent_id: UUID = field(foreign_key=(MyFKParent, 'id'))


@entity
class MyFKChildCascade:
    id: UUID = field(primary_key=True)
    parent_id: UUID = field(foreign_key=(MyFKParent, 'id'), cascade_delete=True)


@entity
class MyFKNoConstraint:
    id: UUID = field(primary_key=True)
    plain: UUID


def _create_table_ddl(entity_type: type) -> str:
    ddl = MySQLDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(entity_type))
    return next(s for s in ddl if s.startswith('CREATE TABLE'))


def _create_index_ddl(entity_type: type, index_name: str) -> str:
    ddl = MySQLDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(entity_type))
    return next(s for s in ddl if s.startswith(f'CREATE INDEX `{index_name}`'))


@fact
@trait('unit', 'mysql')
def mysql_ddl_emits_foreign_key_constraint() -> None:
    ddl = _create_table_ddl(MyFKChild)
    assert 'FOREIGN KEY (`parent_id`) REFERENCES `MyFKParents`(`id`)' in ddl, f'FK clause missing: {ddl}'


@fact
@trait('unit', 'mysql')
def mysql_ddl_emits_cascade_delete_when_configured() -> None:
    ddl = _create_table_ddl(MyFKChildCascade)
    assert 'FOREIGN KEY (`parent_id`) REFERENCES `MyFKParents`(`id`) ON DELETE CASCADE' in ddl, f'cascade FK clause missing: {ddl}'


@fact
@trait('unit', 'mysql')
def mysql_ddl_omits_foreign_key_when_not_configured() -> None:
    ddl = _create_table_ddl(MyFKNoConstraint)
    assert 'FOREIGN KEY' not in ddl, f'unexpected FK clause: {ddl}'
    assert 'ON DELETE CASCADE' not in ddl, f'unexpected cascade clause: {ddl}'


@fact
@trait('unit', 'mysql')
def mysql_ddl_composite_index_fields_ordered_by_rank() -> None:
    @entity
    class MyRankOrderedEntity:
        id: UUID = field(primary_key=True)
        zebra: str = field(index=IndexOptions(name='ix_myrank', rank=0))
        apple: str = field(index=IndexOptions(name='ix_myrank', rank=1))
    ddl = _create_index_ddl(MyRankOrderedEntity, 'ix_myrank')
    expected = 'CREATE INDEX `ix_myrank` ON `MyRankOrderedEntities` (`zebra` ASC, `apple` ASC)'
    assert ddl == expected, f'(expected={expected}, actual={ddl})'


@fact
@trait('unit', 'mysql')
def mysql_ddl_composite_index_equal_ranks_sorted_alphabetically() -> None:
    @entity
    class MyEqualRankEntity:
        id: UUID = field(primary_key=True)
        last_name: str = field(index=IndexOptions(name='ix_myequal', rank=1))
        first_name: str = field(index=IndexOptions(name='ix_myequal', rank=1))
    ddl = _create_index_ddl(MyEqualRankEntity, 'ix_myequal')
    expected = 'CREATE INDEX `ix_myequal` ON `MyEqualRankEntities` (`first_name` ASC, `last_name` ASC)'
    assert ddl == expected, f'(expected={expected}, actual={ddl})'


@fact
@trait('unit', 'mysql')
def mysql_ddl_field_in_multiple_indexes() -> None:
    @entity
    class MyMultiIndexEntity:
        id: UUID = field(primary_key=True)
        status: str = field(index=[IndexOptions(name='ix_mystatus_created', rank=0), 'ix_mystatus_only'])
        created: str = field(index=IndexOptions(name='ix_mystatus_created', rank=1))
    expected_a = 'CREATE INDEX `ix_mystatus_created` ON `MyMultiIndexEntities` (`status` ASC, `created` ASC)'
    assert _create_index_ddl(MyMultiIndexEntity, 'ix_mystatus_created') == expected_a, f'missing or malformed {expected_a}'
    expected_b = 'CREATE INDEX `ix_mystatus_only` ON `MyMultiIndexEntities` (`status` ASC)'
    assert _create_index_ddl(MyMultiIndexEntity, 'ix_mystatus_only') == expected_b, f'missing or malformed {expected_b}'
