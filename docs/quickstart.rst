Quick Start
===========
.. _quickstart:


Installation
============

You can install ``deev`` from PyPI through the usual means, such as ``pip``:

.. code-block:: bash

    pip install deev


Usage
=====

Two popular use cases are shown: using Python objects for CRUD operations, and using the ``db-migrate`` CLI tool to manage DB schema.

Entity CRUD
-----------

.. code-block:: python

    # imports
    from deev import entity, field

    # define a simple entity with an auto-increment PK, an int value column,
    # and a list[str] column
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
        entity_key = table.create(
            SimpleEntity(
                column1=1,
                column2=[3, 2, 1]
            )
        )

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
        entity_key = table.upsert(
            SimpleEntity(
                column1=2,
                column2=[5]
            )
        )
        entity_key = table.upsert(
            SimpleEntity(
                column1=2,
                column2=[6]
            )
        )
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

        # query kwargs are optional; this creates a generator for all table records:
        results = table.query()


CLI ``db-migrate`` Tool
-----------------------

The ``db-migrate`` tool can be used to apply a migration script or undo a previously applied migration script. Here is the main syntax from CLI help:

.. code-block:: bash

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
    usage: db-migrate apply [-h] connectionstring [path] [--stop-at name]
    positional arguments:
      connectionstring  Database connection string.
      path              Directory containing migration scripts (optional). If omitted, a path is calculated from the connectionstring argument, ie. `./migrations/databnase_name/`.
    options:
      -h, --help        show this help message and exit
      --stop-at name    Stop processing at the named migration.

A migration script is a Python file which defines two functions ``apply(...)`` and ``undo(...)``, each receiving a ``DbTransactionContext`` you can use to modify the database transactionally.  As an example, let's assume we modified ``SimpleEntity`` with an additional attribute ``column3`` of type ``datetime``:

.. code-block:: python

    @entity
    class SimpleEntity:
        id: int = field(autoincrement=True, primary_key=True)
        column1: int
        column2: list[str]
        column3: Optional[datetime] = field(nullable=True)

Since we already have a table for this entity, we want to alter the schema to support the new attribute:

.. code-block:: python

    # 000_test01.py
    from deev.common import DbTransactionContext

    def apply(transaction: DbTransactionContext) -> None:
        # alter the existing entity table
        transaction.execute_nonquery('ALTER TABLE SimpleEntity ADD COLUMN column3 DATETIME')
        transaction.commit()

    def undo(transaction: DbTransactionContext) -> None:
        # undo the alteration applied by ``apply(...)`` above
        transaction.execute_nonquery('ALTER TABLE SimpleEntity DROP COLUMN column3')
        transaction.commit()

Apply the change to the existing database:

.. code-block:: bash

    # apply schema change
    db-migrate apply ./test_data/migrations \
        'Server=./test_data/;Database=sqlite3/test.db;Provider=sqlite3'

The tool reports:

.. code-block:: text

    ..apply migration "000_test01"
    Migrations applied 1, skipped 0, available 1.

Undo the change after it has been applied:

.. code-block:: bash

    # undo schema change
    db-migrate undo ./test_data/migrations \
        'Server=./test_data/;Database=sqlite3/test.db;Provider=sqlite3'

The tool reports:

.. code-block:: text

    ..apply migration "000_test01"
    Migrations undone 1, skipped 0, available 1.

