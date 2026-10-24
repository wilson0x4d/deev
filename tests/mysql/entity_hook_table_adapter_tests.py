# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev import entity, field
from deev.common import ConnectionString
from deev.mysql.mysql_table_adapter import MySQLTableAdapter
from deev.utils import connect, create_database
from punit import fact, trait
from uuid import uuid4


@fact
@trait('mysql')
@trait('integration')
def hook_fires_on_new_table_and_skips_existing() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mysql_test)
    cxnstring.database = f'deev_test_{uuid4().hex}'
    create_database(cxnstring)
    calls = []
    try:
        @entity(table_name='tbl_my_hook')
        class HookEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(table_adapter.__class__.__name__)
                table_adapter.create(name='seeded')

        with connect(cxnstring) as connection:
            adapter = MySQLTableAdapter[HookEntity](connection)
            adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'MySQLTableAdapter', f"(expected='MySQLTableAdapter', actual={calls[0]})"
            row = adapter.read(id=1)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded', f"(expected='seeded', actual={row.name})"

            adapter.create_table()
            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        with connect(cxnstring) as connection:
            cursor = connection.cursor()
            cursor.execute(f'DROP DATABASE {cxnstring.database};')
            connection.commit()
            connection.close()
