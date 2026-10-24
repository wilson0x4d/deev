# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev import entity, field
from deev.common import ConnectionString
from deev.clickhouse import ClickHouseProxyConnection, ClickHouseTableAdapter
from deev.utils import connect, create_database
from punit import fact, trait
from uuid import uuid4


@fact
@trait('clickhouse')
@trait('integration')
def hook_fires_on_new_table_and_skips_existing() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    calls = []
    seeded_id = uuid4().hex
    try:
        @entity(table_name='tbl_ch_hook')
        class HookEntity:
            id: str = field(primary_key=True)
            name: str | None = None

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(table_adapter.__class__.__name__)
                table_adapter.create(id=seeded_id, name='seeded')

        with connect(cxnstring) as connection:
            assert isinstance(connection, ClickHouseProxyConnection)
            adapter = ClickHouseTableAdapter[HookEntity](connection)
            adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'ClickHouseTableAdapter', f"(expected='ClickHouseTableAdapter', actual={calls[0]})"
            row = adapter.read(id=seeded_id)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded', f"(expected='seeded', actual={row.name})"

            adapter.create_table()
            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass
