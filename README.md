
[![deev on PyPI](https://img.shields.io/pypi/v/deev.svg)](https://pypi.org/project/deev/) [![deev on readthedocs](https://readthedocs.org/projects/deev/badge/?version=latest)](https://deev.readthedocs.io)

**deev** (דיב) is an entity framework for Python.

This README is only a high-level introduction to **deev**. For more detailed documentation, please view the official docs at [https://deev.readthedocs.io](https://deev.readthedocs.io).


## Features

* Entity-based; perform CRUD operations using Python objects instead of hand-crafting SQL.
* Validation; Entities validate before they get persisted to a database, also validate entities on-demand.
* Transaction Contexts; enter and exit transaction scopes with language-level context management, avoid mismanaged transaction states.
* DB Migrations; use Python code to apply (and undo) schema changes, data translation, etc using `db-migrate` CLI tool for use from CI/CD pipelines.
* PEP 249 compatible abstractions; no need to refactor code just to switch DBMS.
* Syntax normalization; parameterize SQL using `%?` instead of provider-specific syntaxes.
* Raw SQL Access; execute raw SQL as-needed, including provider/DBMS-specific functions (primarily intended for advanced `db-migrate` cases.)


## Installation

You can install `deev` from [PyPI](https://pypi.org/project/deev/) through usual means, such as `pip`:

```bash
    pip install deev
```


## Usage

Let's have a look at the two popular use cases: using Python objects for CRUD operations, and using the `db-migrate` CLI tool to manage DB schema.

### Entity CRUD

First, let's define a "SimpleEntity" class we will use as a database entity:

```python
    from datetime import datetime, timezone
    from deev import entity, field
    from typing import Optional    

    # ./SimpleEntity.py
    @entity
    class SimpleEntity:
        column1: int
        column2: Optional[list[str]] = field(default=None)
        column3: Optional[datetime] = field(default=lambda: datetime.now(timezone.utc))
        id: int = field(autoincrement=True, default=None, primary_key=True)
```

Next, let's write some CRUD-based code:

```python
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
        entity_key = table.create(SimpleEntity(
            column1=1,
            column2=[3, 2, 1]
        ))
        # READ
        entity = table.read(**entity_key)
        assert entity.id is not None
        assert entity.column1 == 1
        assert entity.column2[0] == 3
        assert entity.column2[1] == 2
        assert entity.column2[2] == 1
        # UPDATE
        entity.column2[1] = 4
        table.update(entity)
        # DELETE
        table.delete(**entity_key)

        # alternatives: upsert + query
        entity_key = table.upsert(SimpleEntity(
            column1=2,
            column2=[5]
        ))
        entity_key = table.upsert(SimpleEntity(
            column1=2,
            column2=[6]
        ))
        results = table.query(
            where='column1 = %?',
            orderby='column1 DESC',
            limit=2,   
            params=(2,)
        )
        count = 0
        for result in results:
            assert result.column2[0] in (5, 6)
            count += 1
        assert count == 2
        # query kwargs are optional, for example this creates a generator for all table records:
        results = table.query()
```

### CLI `db-migrate` Tool

The `db-migrate` tool can be used to apply a migration script or undo a previously applied migration script.

Basic syntax:

```bash
$ db-migrate -h
usage: db-migrate [-h] [--verbose] <COMMAND> ...

Utility for applying, undoing, or generating migrations.

positional arguments:
  <COMMAND>   Action to perform.
    apply     Apply migrations.
    undo      Undo migrations.

options:
  -h, --help  show this help message and exit
  --verbose   Enable verbose logging.

$ db-migrate apply -h
usage: db-migrate apply [-h] [--stop-at name] connectionstring [path]

positional arguments:
  connectionstring  Database connection string.
  path              Directory containing migration scripts (optional). If omitted, a path is calculated from the connectionstring argument, ie.
                    `./migrations/databnase_name/`.

options:
  -h, --help        show this help message and exit
  --stop-at name    Stop processing at the named migration.

```

A migration script is a Python file which defines two functions `apply(...)` and `undo(...)`, each receiving a `DbTransactionContext` you can use to modify the database transactionally.  As an example let's assume we modified `SimpleEntity` with an additional attribute `column3` of type `datetime`:

Since we already have a table for this entity, we want to modify the schema to support the new attribute:

```python
    # ./migrations/test_db/000_initial_schema.py
    from deev.common import DbTransactionContext
    from deev.utils import create_table_adapter
    from .SimpleEntity import SimpleEntity

    def apply(transaction: DbTransactionContext) -> None:
        table_adapter = create_table_adapter(SimpleEntity, transaction)
        table_adapter.create_table()
        transaction.commit()

    def undo(transaction: DbTransactionContext) -> None:
        transaction.execute_nonquery('DROP TABLE `SimpleEntities`;')
        transaction.commit()
```

```python
    # ./migrations/test_db/001_initial_seed.py
    from deev.common import DbTransactionContext
    from deev.utils import create_table_adapter
    from .SimpleEntity import SimpleEntity

    def apply(transaction: DbTransactionContext) -> None:
        table_adapter = create_table_adapter(SimpleEntity, transaction)
        table_adapter.create(SimpleEntity(
            column1 = 345
        ))
        table_adapter.create(SimpleEntity(
            column1 = 456
        ))
        transaction.commit()

    def undo(transaction: DbTransactionContext) -> None:
        transaction.execute_nonquery('DELETE FROM `SimpleEntities` WHERE `column1` IN (345, 456)')
        transaction.commit()
```

Finally, we can apply the change to our existing database:

```bash
    # apply schema change
    db-migrate apply 'Server=./test_data/;Database=sqlite3/test.db;Provider=sqlite3' ./migrations/test_db/
```
```
    ..apply migration "000_initial_schema"
    ..apply migration "001_initial_seed"
    Migrations applied 2, skipped 0, available 2.
```

We can also undo the change after it has been applied:

```bash
    # undo schema change
    db-migrate undo 'Server=./test_data/;Database=sqlite3/test.db;Provider=sqlite3' ./migration/test_db/
```
```
    ..undo migration "001_initial_seed"
    ..undo migration "000_initial_schema"
    Migrations undone 2, skipped 0, available 2.
```

## Contact

You can reach me on [Discord](https://discordapp.com/users/307684202080501761) or [open an Issue on Github](https://github.com/wilson0x4d/deev/issues/new/choose).
