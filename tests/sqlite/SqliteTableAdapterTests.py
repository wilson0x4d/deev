# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.sqlite import SqliteTableAdapter
import os
from punit import fact, trait
import shutil
from typing import Any, Optional
from uuid import UUID, uuid4


@fact
@trait('sqlite3')
@trait('integration')
def basic_verification() -> None:
    #
    # mutate configuration to generate a unique database
    #
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connectionStrings.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    try:
        @entity
        class BasicEntity:
            id: int = field(autoincrement=True, primary_key=True, default=0)
            example: Optional[int] = None
            example_text: Optional[str] = None
            other: Optional[UUID] = None
            another: Optional[bool] = None
            floaty: Optional[float] = None
            backed_value: Optional[int] = None
            x: Optional[dict[str, Any]] = None
            y: Optional[list[int]] = None
            z: Optional[tuple[str, int]] = None
            dt: Optional[datetime] = None
            td: Optional[timedelta] = None
        with connect(cxnstring) as connection:
            #
            # ..create a table adapter _and_ create a backing table for `BasicEntity`
            #
            adapter = SqliteTableAdapter[BasicEntity](connection)
            adapter.create_table()
            #
            # ..create a BasicEntity instance in the database
            #
            entity1 = BasicEntity(
                example=123,
                other=uuid4(),
                dt=datetime.now(tz=timezone.utc)
            )
            entity_key = adapter.create(entity1)
            #
            # ..assert a valid key has been returned
            #
            assert entity_key is not None
            assert entity_key.get('id') is not None
            assert entity_key.get('id', 0) > 0
            #
            # ..assert we can read the entity back using the key
            #
            data = adapter.read(**entity_key)
            assert data is not None
            #
            # ..assert we can mutate the entity
            data.example_text = 'updated'
            adapter.upsert(data)
            data = adapter.read(**entity_key)
            assert data is not None
            assert data.example_text == 'updated'
            assert data.example == entity1.example
            assert data.other is not None
            assert entity1.other is not None
            assert data.other.hex == entity1.other.hex
            #
            # ..assert we can query for the entity
            #
            selected = []
            for row in adapter.query(
                where='example_text=%?',
                params=['updated'],
                orderby='id DESC'
            ):
                selected.append(row)
            assert len(selected) > 0
            #
            # ..assert deletions
            #
            adapter.delete(**entity_key)
            existence = adapter.exists(**entity_key)
            assert existence is False
    finally:
        #
        # ..remove the test database we created
        #
        database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
        assert os.path.exists(database_path)
        shutil.rmtree(database_path)
        assert not os.path.exists(database_path)
