# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev import entity, field
from deev.entities import get_entity_spec
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
