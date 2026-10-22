# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev import entity, field
from deev.entities import get_entity_spec, IndexOptions
from deev.mssql import MSSQLDDLGenerator
from punit import fact, trait
from uuid import UUID


@entity
class MsFKParent:
    id: UUID = field(primary_key=True)


@entity
class MsFKChild:
    id: UUID = field(primary_key=True)
    parent_id: UUID = field(foreign_key=(MsFKParent, 'id'))


@entity
class MsFKChildCascade:
    id: UUID = field(primary_key=True)
    parent_id: UUID = field(foreign_key=(MsFKParent, 'id'), cascade_delete=True)


@entity
class MsFKNoConstraint:
    id: UUID = field(primary_key=True)
    plain: UUID


def _create_table_ddl(entity_type: type) -> str:
    ddl = MSSQLDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(entity_type))
    return next(s for s in ddl if s.startswith('CREATE TABLE'))


def _create_index_ddl(entity_type: type, index_name: str) -> str:
    ddl = MSSQLDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(entity_type))
    return next(s for s in ddl if s.startswith(f'CREATE INDEX [{index_name}]'))


@fact
@trait('unit', 'mssql')
def mssql_ddl_emits_foreign_key_constraint() -> None:
    ddl = _create_table_ddl(MsFKChild)
    assert 'FOREIGN KEY ([parent_id]) REFERENCES [MsFKParents]([id])' in ddl, f'FK clause missing: {ddl}'


@fact
@trait('unit', 'mssql')
def mssql_ddl_emits_cascade_delete_when_configured() -> None:
    ddl = _create_table_ddl(MsFKChildCascade)
    assert 'FOREIGN KEY ([parent_id]) REFERENCES [MsFKParents]([id]) ON DELETE CASCADE' in ddl, f'cascade FK clause missing: {ddl}'


@fact
@trait('unit', 'mssql')
def mssql_ddl_omits_foreign_key_when_not_configured() -> None:
    ddl = _create_table_ddl(MsFKNoConstraint)
    assert 'FOREIGN KEY' not in ddl, f'unexpected FK clause: {ddl}'
    assert 'ON DELETE CASCADE' not in ddl, f'unexpected cascade clause: {ddl}'


@fact
@trait('unit', 'mssql')
def mssql_ddl_composite_index_fields_ordered_by_rank() -> None:
    @entity
    class MsRankOrderedEntity:
        id: UUID = field(primary_key=True)
        zebra: str = field(index=IndexOptions(name='ix_msrank', rank=0))
        apple: str = field(index=IndexOptions(name='ix_msrank', rank=1))
    ddl = _create_index_ddl(MsRankOrderedEntity, 'ix_msrank')
    expected = 'CREATE INDEX [ix_msrank] ON [MsRankOrderedEntities] ([zebra] ASC, [apple] ASC)'
    assert ddl == expected, f'(expected={expected}, actual={ddl})'


@fact
@trait('unit', 'mssql')
def mssql_ddl_composite_index_equal_ranks_sorted_alphabetically() -> None:
    @entity
    class MsEqualRankEntity:
        id: UUID = field(primary_key=True)
        last_name: str = field(index=IndexOptions(name='ix_msequal', rank=1))
        first_name: str = field(index=IndexOptions(name='ix_msequal', rank=1))
    ddl = _create_index_ddl(MsEqualRankEntity, 'ix_msequal')
    expected = 'CREATE INDEX [ix_msequal] ON [MsEqualRankEntities] ([first_name] ASC, [last_name] ASC)'
    assert ddl == expected, f'(expected={expected}, actual={ddl})'


@fact
@trait('unit', 'mssql')
def mssql_ddl_field_in_multiple_indexes() -> None:
    @entity
    class MsMultiIndexEntity:
        id: UUID = field(primary_key=True)
        status: str = field(index=[IndexOptions(name='ix_msstatus_created', rank=0), 'ix_msstatus_only'])
        created: str = field(index=IndexOptions(name='ix_msstatus_created', rank=1))
    expected_a = 'CREATE INDEX [ix_msstatus_created] ON [MsMultiIndexEntities] ([status] ASC, [created] ASC)'
    assert _create_index_ddl(MsMultiIndexEntity, 'ix_msstatus_created') == expected_a, f'missing or malformed {expected_a}'
    expected_b = 'CREATE INDEX [ix_msstatus_only] ON [MsMultiIndexEntities] ([status] ASC)'
    assert _create_index_ddl(MsMultiIndexEntity, 'ix_msstatus_only') == expected_b, f'missing or malformed {expected_b}'


@fact
@trait('unit', 'mssql')
def mssql_ddl_unique_index_resolution() -> None:
    @entity
    class MsUniqueResolutionEntity:
        id: UUID = field(primary_key=True)
        email: str = field(index=IndexOptions(name='ix_uniq_opts', unique=True))
        code: str = field(unique=True, index='ix_uniq_field')
        overridden: str = field(unique=True, index=IndexOptions(name='ix_uniq_override', unique=False, rank=0))
        plain: str = field(index=IndexOptions(name='ix_uniq_override', rank=1))
        any_unique_a: str = field(index='ix_uniq_any')
        any_unique_b: str = field(unique=True, index='ix_uniq_any')
    ddl = MSSQLDDLGenerator().generate_table_ddl(entity_spec=get_entity_spec(MsUniqueResolutionEntity))
    expected_opts = 'CREATE UNIQUE INDEX [ix_uniq_opts] ON [MsUniqueResolutionEntities] ([email] ASC)'
    assert expected_opts in ddl, f'missing: {expected_opts}, got: {ddl}'
    expected_field = 'CREATE UNIQUE INDEX [ix_uniq_field] ON [MsUniqueResolutionEntities] ([code] ASC)'
    assert expected_field in ddl, f'missing: {expected_field}, got: {ddl}'
    expected_override = 'CREATE INDEX [ix_uniq_override] ON [MsUniqueResolutionEntities] ([overridden] ASC, [plain] ASC)'
    assert expected_override in ddl, f'missing: {expected_override}, got: {ddl}'
    assert 'CREATE UNIQUE INDEX [ix_uniq_override]' not in ddl, f'override to non-unique not honored: {ddl}'
    expected_any = 'CREATE UNIQUE INDEX [ix_uniq_any] ON [MsUniqueResolutionEntities] ([any_unique_a] ASC, [any_unique_b] ASC)'
    assert expected_any in ddl, f'missing: {expected_any}, got: {ddl}'
