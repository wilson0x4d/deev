# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString, DbAdapter
from deev.entities import entity, field
from deev.sqlite import SQLiteTableAdapter
from deev.utils import connect, create_database, drop_database, generate_dbadapter_ddl
from punit import fact, trait
from uuid import uuid4


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


@fact
@trait('integration')
@trait('sqlite')
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    drop_database(cxnstring)
