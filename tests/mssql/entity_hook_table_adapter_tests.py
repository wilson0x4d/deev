# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev import entity, field
from deev.common import ConnectionString
from deev.mssql.mssql_table_adapter import MSSQLTableAdapter
from deev.utils import connect
from punit import fact, trait
from uuid import uuid4


@fact
@trait('mssql')
@trait('integration')
def hook_fires_on_new_table_and_skips_existing() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mssql_test)
    table_name = f'tbl_ms_hook_{uuid4().hex[:6]}'
    calls = []
    try:
        @entity(table_name=table_name)
        class HookEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            name: str | None = None

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(table_adapter.__class__.__name__)
                table_adapter.create(name='seeded')

        with connect(cxnstring) as connection:
            adapter = MSSQLTableAdapter[HookEntity](connection)
            adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'MSSQLTableAdapter', f"(expected='MSSQLTableAdapter', actual={calls[0]})"
            row = adapter.read(id=1)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded', f"(expected='seeded', actual={row.name})"

            adapter.create_table()
            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP TABLE [{table_name}];')
                connection.commit()
        except Exception:
            pass
