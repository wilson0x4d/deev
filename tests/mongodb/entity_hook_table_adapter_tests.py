# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev import entity, field
from deev.common import ConnectionString
from deev.mongodb import MongoProxyConnection
from deev.mongodb.mongo_table_adapter import MongoTableAdapter
from deev.utils import connect
from punit import fact, trait
from uuid import uuid4


@fact
@trait('mongodb')
@trait('integration')
def hook_fires_on_new_collection_and_skips_existing() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.mongo_test)
    collection_name = f'tbl_mdb_hook_{uuid4().hex[:6]}'
    calls = []
    seeded_id = uuid4().hex
    try:
        @entity(table_name=collection_name)
        class HookEntity:
            id: str = field(primary_key=True)
            name: str | None = None

            @staticmethod
            def on_create_table(table_adapter) -> None:
                calls.append(table_adapter.__class__.__name__)
                table_adapter.create(id=seeded_id, name='seeded')

        with connect(cxnstring) as connection:
            adapter = MongoTableAdapter[HookEntity](connection)
            adapter.create_table()

            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
            assert calls[0] == 'MongoTableAdapter', f"(expected='MongoTableAdapter', actual={calls[0]})"
            row = adapter.read(id=seeded_id)
            assert row is not None, '(expected seeded row, actual=None)'
            assert row.name == 'seeded', f"(expected='seeded', actual={row.name})"

            adapter.create_table()
            assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    finally:
        try:
            with connect(cxnstring) as connection:
                assert isinstance(connection, MongoProxyConnection)
                connection.mongo_client[connection.mongo_database_name].drop_collection(collection_name)
        except Exception:
            pass
