Database Migration
==================

.. _migration:

What is Database Migration?
---------------------------

Database migration is the process of versioning and applying incremental schema or data changes to a database. Rather than editing a database manually, migrations are expressed as ordered scripts — each one describing a single, reversible step — that move the database from its current state to a desired target.

Migrations are essential for:

* **Reproducibility** — any environment (development, CI/CD, production) can reach the same schema by running all migrations in order.
* **Version control** — migration scripts live in source control alongside application code, making schema changes reviewable and auditable.
* **Safety** — every ``apply()`` has a corresponding ``undo()``, allowing rollbacks when something goes wrong.
* **Idempotency** — the migrator tracks which migrations have already run and skips them, so re-running is safe.


The ``db-migrate`` Tool
-----------------------

The ``db-migrate`` CLI (provided by deev) applies or undoes migrations across supported database providers: MySQL, SQLite, and MongoDB.

Installation
~~~~~~~~~~~~

Install deev from PyPI:

.. code-block:: bash

    pip install deev


CLI Syntax
~~~~~~~~~~

.. code-block:: bash

    $ db-migrate -h
    usage: db-migrate [-h] [--verbose] <COMMAND> ...

    Utility for applying, undoing, or generating migrations.

    positional arguments:
        <COMMAND>   Action to perform.
            apply     Apply migrations.
            undo      Undo migrations.


.. code-block:: bash

    $ db-migrate apply -h
    usage: db-migrate apply [-h] [--stop-at name] connectionstring [path]

    positional arguments:
        connectionstring  Database connection string (name from config or literal ``key=value`` format).
        path              Directory containing migration scripts (optional). If omitted, defaults to ``./migrations/<database_name>/``.

    options:
        -h, --help            show this help message
        --stop-at name        Stop processing at the named migration. Use "all" to process every migration.


.. code-block:: bash

    $ db-migrate undo -h
    usage: db-migrate undo [-h] [--stop-at name] connectionstring [path]

    positional arguments:
        connectionstring  Database connection string (name from config or literal ``key=value`` format).
        path              Directory containing migration scripts (optional). If omitted, defaults to ``./migrations/<database_name>/``.

    options:
        -h, --help            show this help message
        --stop-at name        Stop undoing at the named migration. Use "all" to undo every applied migration.


Connection Strings
~~~~~~~~~~~~~~~~~~

The ``connectionstring`` argument can be a literal connection string or the name of a stored connection configured via **appsettings2**:

.. code-block:: bash

    # Literal connection string (contains '=')
    db-migrate apply all 'Server=.;Database=mydb;Provider=sqlite3' ./migrations/

    # Named connection from config (no '=')
    db-migrate apply all my_production

When using a named connection, deev looks up ``connectionStrings__<name>`` or ``connections__<name>`` in the active appsettings2 configuration.


Migration Scripts
-----------------

A migration script is a plain Python ``.py`` file placed in a migration directory (e.g. ``./migrations/mydb/``). Each file must define two functions:

.. code-block:: python

    def apply(db_transaction: DbTransactionContext) -> None:
        """Apply this migration's changes."""
        ...

    def undo(db_transaction: DbTransactionContext) -> None:
        """Revert the changes made by ``apply()``."""
        ...


Naming and Ordering
~~~~~~~~~~~~~~~~~~~

The migrator scans all ``*.py`` files in the migration directory and processes them in **alphabetical order** during ``apply``, and **reverse alphabetical order** during ``undo``. File *names* (not file modification times) determine ordering, so prefix your filenames:

.. code-block:: none

    migrations/mydb/
        001_create_users.py
        002_add_email_column.py
        003_seed_initial_data.py


Tracking Applied Migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~

After each ``apply()``, the migrator records the migration name in a special table called ``_migrationdata`` (SQL) or collection ``_migrationdata`` (MongoDB). This allows the tool to identify which migrations have already been applied and skip them on subsequent runs.


Implementing Migration Scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``apply()`` and ``undo()`` functions each receive a :class:`~deev.common.DbTransactionContext` — a transaction context object exposing database operations. All changes within a single migration are wrapped in a transaction, which the migrator commits after the function returns (or rolls back if an exception propagates).

**You must call ``commit()`` explicitly inside your migration.** The migrator does not commit on behalf of the migration script; if you forget to call ``commit()``, the migration context's exit handler will raise a ``DbError``.


Basic Example: Creating a Table
"""""""""""""""""""""""""""""""

.. code-block:: python

    # migrations/mydb/001_create_users.py
    from deev.common import DbTransactionContext

    def apply(db_transaction: DbTransactionContext) -> None:
        db_transaction.execute_nonquery(
            'CREATE TABLE IF NOT EXISTS users ('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  name TEXT(256) NOT NULL'
            ')'
        )
        db_transaction.commit()

    def undo(db_transaction: DbTransactionContext) -> None:
        db_transaction.execute_nonquery('DROP TABLE IF EXISTS users')
        db_transaction.commit()


Using Table Adapters
""""""""""""""""""""

You can use deev's table adapters inside migration scripts for type-safe operations:

.. code-block:: python

    # migrations/mydb/002_add_index.py
    from deev.common import DbTransactionContext
    from deev.utils import create_table_adapter
    from myapp.entities import User

    def apply(db_transaction: DbTransactionContext) -> None:
        table = create_table_adapter(User, db_transaction)
        # Use table adapter methods for type-safe CRUD
        for name in ('Alice', 'Bob'):
            table.create(User(name=name))
        db_transaction.commit()

    def undo(db_transaction: DbTransactionContext) -> None:
        db_transaction.execute_nonquery('DELETE FROM `users`')
        db_transaction.commit()


Raw SQL with Parameters
"""""""""""""""""""""""

deev normalizes parameter syntax to ``%?`` across all providers. The transaction context handles provider-specific translation internally:

.. code-block:: python

    def apply(db_transaction: DbTransactionContext) -> None:
        db_transaction.execute_nonquery(
            'INSERT INTO users (name) VALUES (%?)',
            ('Charlie',)
        )
        db_transaction.commit()


Provider-Specific Considerations
--------------------------------


MySQL
~~~~~

**DDL auto-commits transactions.** MySQL implicitly commits any active transaction before executing DDL statements such as ``CREATE``, ``DROP``, ``ALTER``, etc. This means that if your migration contains both DML and DDL, the DML changes before the DDL are committed automatically — you cannot roll them back together as a single atomic unit.

The transaction context detects DDL statements and manages savepoints defensively:

* Savepoints created **before** a DDL statement are released when MySQL auto-commits.
* If a rollback is needed after DDL, the context falls back to a full ``ROLLBACK`` instead of ``ROLLBACK TO SAVEPOINT``.
* Nested transactions use savepoint names prefixed with ``TID_<uuid>`` (e.g., ``TID_3f7a8b2c...``).

**Implication for migration writers:** If you need an atomic operation that combines DDL and data changes, consider splitting them into separate migration scripts so the DDL runs first in one script and the data operations run in a subsequent script within a clean transaction.


SQLite
~~~~~~

SQLite also implicitly commits before DDL statements — the same concern as MySQL applies here. The :class:`~deev.sqlite.SqliteTransactionContext` handles this by catching ``sqlite3.OperationalError`` on savepoint release and falling back to a full ``COMMIT`` when DDL has killed all savepoints.

**Parameter syntax:** SQLite uses ``?`` placeholders natively. The deev transaction context automatically translates the normalized ``%?`` syntax to ``?``, so you always write ``%?`` in migrations regardless of provider.


MongoDB
~~~~~~~

**No DDL concept.** MongoDB is a schema-less document store, so there are no DDL statements that implicitly commit. All operations within a migration's transaction are wrapped in a real ``pymongo.ClientSession.start_transaction()``.

* Nested (savepoint-level) transactions are **NOPs** — only the top-level ambient transaction matters. Calling ``commit()`` or ``rollback()`` from nested scopes is a no-op; the parent scope handles the actual commit/abort.
* The migration context exposes additional MongoDB-specific properties via the transaction object:

.. code-block:: none

    db_transaction.mongo_client     # pymongo.MongoClient instance
    db_transaction.mongo_database   # pymongo.database.Database instance
    db_transaction.mongo_session    # pymongo.ClientSession instance
    db_transaction.mongo_database_name  # str


* Collections are created implicitly on first insert — no ``CREATE COLLECTION`` statement exists in MongoDB.


Migration Data Entity
"""""""""""""""""""""

The ``_migrationdata`` entity differs by provider:

* **MySQL / SQLite** — uses an integer auto-increment primary key.
* **MongoDB** — uses a UUID primary key, since MongoDB does not support ``AUTO_INCREMENT``.


Transaction Behavior Summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following table summarizes the transaction behavior across providers during migration execution:

+--------------------------+----------------------------------+----------------------------------+-----------------------------------+
| Aspect                   | MySQL                            | SQLite                           | MongoDB                           |
+==========================+==================================+==================================+===================================+
| DDL auto-commit          | **Yes** — implicit before        | **Yes** — implicit before        | N/A (no DDL)                      |
|                          | ``CREATE``, ``DROP``,            | ``CREATE``, ``DROP``,            |                                   |
|                          | ``ALTER``, etc.                  | ``ALTER``, etc.                  |                                   |
+--------------------------+----------------------------------+----------------------------------+-----------------------------------+
| Savepoint recovery       | Falls back to full               | Catches ``OperationalError``;    | N/A                               |
| after DDL                | ``ROLLBACK`` on                  | falls back to full ``COMMIT``.   |                                   |
|                          | rollback failure                 |                                  |                                   |
+--------------------------+----------------------------------+----------------------------------+-----------------------------------+
| Nested transactions      | ``SAVEPOINT TID_<uuid>``         | ``SAVEPOINT TID_<uuid>``         | NOP — parent handles              |
| mechanism                |                                  |                                  | everything                        |
+--------------------------+----------------------------------+----------------------------------+-----------------------------------+
| Top-level commit         | ``self.__context.commit()``      | ``COMMIT``                       | ``mongo_session.                  |
|                          |                                  |                                  | commit_transaction()``            |
+--------------------------+----------------------------------+----------------------------------+-----------------------------------+
| Parameter syntax         | Provider-native (via             | ``%?`` → ``?`` auto-translation  | Passed through                    |
| in migrations            | mysql.connector)                 |                                  |                                   |
+--------------------------+----------------------------------+----------------------------------+-----------------------------------+


Best Practices
--------------

1. **Always provide an ``undo()``.** Every migration should be reversible. If you cannot undo a change safely, document why clearly as a comment.
2. **Name migrations for sort order.** Use numeric prefixes (``001_``, ``002_``, ...) or date-based names (``2026-06-15_add_index``) to guarantee ordering.
3. **Keep migrations idempotent.** Where possible, use ``IF NOT EXISTS`` / ``IF EXISTS`` guards so re-running is safe.
4. **Commit explicitly inside every migration function.** The migrator requires the migration script to call ``commit()``; failing to do so will raise a ``DbError`` when the context exits.
5. **Be aware of DDL auto-commit on MySQL and SQLite.** Do not assume DML changes before DDL in the same migration are part of the same atomic transaction — split them into separate migration scripts if atomicity matters.
6. **Use the normalized ``%?`` parameter placeholder** regardless of provider — deev handles the translation internally.
