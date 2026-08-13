# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import datetime, timezone
from deev import entity, field
from punit import fact
from typing import cast


@entity
class SimpleEntity:
    # aka "./SimpleEntity.py" from README
    id: int = field(autoincrement=True, primary_key=True)
    column1: int
    column2: list[str] | None = field(default=None)
    column3: datetime | None = field(default=lambda: datetime.now(timezone.utc))


@fact
def docs_example_bvt() -> None:
    # imports
    from deev import entity, field

    # define a simple entity with an auto-increment PK, an int value column, and a list[str] column
    @entity
    class SimpleEntity:
        id: int = field(autoincrement=True, primary_key=True)
        column1: int
        column2: list[str]

    # create a database using familiar connection-string syntax
    from deev.utils import create_database

    connection_str = 'Server=./test_data/;Database=sqlite3/test.db;Provider=sqlite3'
    create_database(connection_str)

    # connect to your database, create a table for storage, and perform some CRUD operations
    from deev import connect
    from deev.sqlite import SqliteTableAdapter
    with connect(connection_str) as db:
        table = SqliteTableAdapter[SimpleEntity](db)
        table.create_table()
        # CREATE
        entity_key = table.create(SimpleEntity(  # type: ignore[call-arg]
            column1=1,
            column2=['3', '2', '1']
        ))
        # READ
        e = table.read(**entity_key)
        assert e is not None
        assert e.id is not None
        assert e.column1 == 1
        assert e.column2[0] == '3'
        assert e.column2[1] == '2'
        assert e.column2[2] == '1'
        # UPDATE
        e.column2[1] = '4'
        table.update(e)
        # DELETE
        table.delete(**entity_key)

        # alternatives: upsert + query
        entity_key = table.upsert(SimpleEntity(  # type: ignore[call-arg]
            column1=2,
            column2=['5']))
        entity_key = table.upsert(SimpleEntity(  # type: ignore[call-arg]
            column1=2,
            column2=['6']
        ))
        results = table.query(
            where='column1 = %?',
            orderby='column1 DESC',
            limit=2,
            params=(2,)
        )
        count = 0
        for result in results:
            assert result.column2[0] in ('5', '6')
            count += 1
        assert count == 2
        # query kwargs are optional, for example this creates a generator for all table records:
        results = table.query()
