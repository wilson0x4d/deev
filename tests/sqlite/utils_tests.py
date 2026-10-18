# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString, DbAdapter
from deev.entities import entity, field
from deev.sqlite import SQLiteTableAdapter
from deev.utils import connect, create_database, drop_database, generate_dbadapter_ddl
from punit import fact, trait
from uuid import UUID, uuid4


@entity
class DDLOrderAlphaEntity:
    id: int = field(primary_key=True, autoincrement=True)
    name: str


@entity
class DDLOrderZetaEntity:
    id: int = field(primary_key=True, autoincrement=True)
    name: str


class DDLOrderDbAdapter(DbAdapter):
    def __init__(self, connection_string: ConnectionString | str):
        super().__init__(connection_string)

    @property
    def zeta(self) -> SQLiteTableAdapter[DDLOrderZetaEntity]:
        return self.get_table_adapter(DDLOrderZetaEntity)  # type: ignore[return-value]

    @property
    def alpha(self) -> SQLiteTableAdapter[DDLOrderAlphaEntity]:
        return self.get_table_adapter(DDLOrderAlphaEntity)  # type: ignore[return-value]


@fact
@trait('unit', 'sqlite')
def generate_dbadapter_ddl_orders_tables_by_table_name() -> None:
    cxnstring = ConnectionString('sqlite:///:memory:')
    ddl = generate_dbadapter_ddl(cxnstring, f'{__name__}.DDLOrderDbAdapter')
    expected = ['DDLOrderAlphaEntities', 'DDLOrderZetaEntities']
    table_names = [stmt.split('[')[1].split(']')[0] for stmt in ddl if stmt.startswith('CREATE TABLE')]
    assert table_names == expected, f'(expected={expected}, actual={table_names})'
    assert table_names == sorted(table_names), f'(expected={sorted(table_names)}, actual={table_names})'


# NOTE: alphabetical order would place Apple before Zebra, but the foreign key
#       requires Zebra to be created first.
@entity
class DDLFKZetaEntity:
    id: UUID = field(primary_key=True)


@entity
class DDLFKAppleEntity:
    id: UUID = field(primary_key=True)
    zeta_id: UUID = field(foreign_key=(DDLFKZetaEntity, 'id'))


class DDLFKDbAdapter(DbAdapter):
    def __init__(self, connection_string: ConnectionString | str):
        super().__init__(connection_string)

    @property
    def apple(self) -> SQLiteTableAdapter[DDLFKAppleEntity]:
        return self.get_table_adapter(DDLFKAppleEntity)  # type: ignore[return-value]

    @property
    def zeta(self) -> SQLiteTableAdapter[DDLFKZetaEntity]:
        return self.get_table_adapter(DDLFKZetaEntity)  # type: ignore[return-value]


@fact
@trait('unit', 'sqlite')
def generate_dbadapter_ddl_orders_foreign_key_targets_first() -> None:
    cxnstring = ConnectionString('sqlite:///:memory:')
    ddl = generate_dbadapter_ddl(cxnstring, f'{__name__}.DDLFKDbAdapter')
    expected = ['DDLFKZetaEntities', 'DDLFKAppleEntities']
    table_names = [stmt.split('[')[1].split(']')[0] for stmt in ddl if stmt.startswith('CREATE TABLE')]
    assert table_names == expected, f'(expected={expected}, actual={table_names})'


# NOTE: the adapter references only the dependent entity; the foreign-key target
#       (not a direct adapter property) must still be emitted, and first.
class DDLFKTransitiveDbAdapter(DbAdapter):
    def __init__(self, connection_string: ConnectionString | str):
        super().__init__(connection_string)

    @property
    def apple(self) -> SQLiteTableAdapter[DDLFKAppleEntity]:
        return self.get_table_adapter(DDLFKAppleEntity)  # type: ignore[return-value]


@fact
@trait('unit', 'sqlite')
def generate_dbadapter_ddl_includes_transitive_foreign_key_targets() -> None:
    cxnstring = ConnectionString('sqlite:///:memory:')
    ddl = generate_dbadapter_ddl(cxnstring, f'{__name__}.DDLFKTransitiveDbAdapter')
    expected = ['DDLFKZetaEntities', 'DDLFKAppleEntities']
    table_names = [stmt.split('[')[1].split(']')[0] for stmt in ddl if stmt.startswith('CREATE TABLE')]
    assert table_names == expected, f'(expected={expected}, actual={table_names})'


@fact
@trait('integration')
@trait('sqlite')
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    drop_database(cxnstring)
