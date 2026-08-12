# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.clickhouse import ClickHouseTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait
from typing import Any, Optional


@fact
@trait('clickhouse')
@trait('integration')
def basic_verification() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    test_db = f'deev_test_{uuid4().hex}'
    cxnstring.database = test_db
    create_database(cxnstring)
    try:
        @entity
        class BasicEntity:
            id: str = field(primary_key=True)
            example: Optional[int] = None
            example_text: Optional[str] = None
            other: Optional[UUID] = None
            another: Optional[bool] = None
            floaty: Optional[float] = None
            backed_value: Optional[int] = None
            x: Optional[dict[str, str]] = None
            y: Optional[list[int]] = None
            z: Optional[tuple[str, int]] = None
            dt: Optional[datetime] = None

        with connect(cxnstring) as connection:
            adapter = ClickHouseTableAdapter[BasicEntity](connection, create_table=True)

            entity1 = BasicEntity(
                id=uuid4().hex,
                example=123,
                other=uuid4(),
                dt=datetime.now(tz=timezone.utc)
            )
            entity_key = adapter.create(entity1)
            assert entity_key is not None
            assert entity_key.get('id') is not None

            data = adapter.read(**entity_key)
            assert data is not None

            data.example_text = 'updated'
            adapter.upsert(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.example_text == 'updated'

            selected = []
            for row in adapter.query(where='exampleText=%?', params=['updated']):
                selected.append(row)
            assert len(selected) > 0

            adapter.delete(**entity_key)
            existence = adapter.exists(**entity_key)
            assert existence is False
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass
