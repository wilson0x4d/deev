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

The ``db-migrate`` CLI (provided by deev) applies or undoes migrations across supported database providers: SQLite, MySQL, MSSQL, MongoDB, and ClickHouse.

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
            generate  Generate DDL.
            undo      Undo migrations.

.. note:: The ``generate`` subcommand is **alpha-quality** and subject to change without notice. Do not rely on its interface for production tooling.


.. code-block:: bash

    $ db-migrate apply -h
    usage: db-migrate apply [-h] migration-name connection [path]

    positional arguments:
        migration-name  The name of the migration at which apply should stop processing. Specify "all" to process all migrations.
        connection      Database connection string (name from config or literal ``key=value`` format).
        path            Directory containing migration scripts (optional). If omitted, a path is calculated from the connection argument, ie. ``./migrations/<database_name>/``.

    options:
        -h, --help        show this help message


.. code-block:: bash

    $ db-migrate undo -h
    usage: db-migrate undo [-h] migration-name connection [path]

    positional arguments:
        migration-name  The name of the migration at which undo should stop processing. Specify "all" to process all migrations.
        connection      Database connection string (name from config or literal ``key=value`` format).
        path            Directory containing migration scripts (optional). If omitted, a path is calculated from the connection argument, ie. ``./migrations/<database_name>/``.

    options:
        -h, --help        show this help message


.. code-block:: bash

    $ db-migrate generate -h
    usage: db-migrate generate [-h] [--emit-use-stmt] type fqn connection

    positional arguments:
        type          The type of object to generate DDL for (entity or database).
        fqn           The fully-qualified type name, ie. ``my_project.my_entities.MyEntity``.
        connection    Database connection string (name from config or literal ``key=value`` format).

    options:
        -h, --help            show this help message
        --emit-use-stmt       Emit a ``USE <database>;`` statement before the generated DDL.


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

After each ``apply()``, the migrator records the migration name in a special table (or collection, for MongoDB and ClickHouse) called ``_migrationdata``. This allows the tool to identify which migrations have already been applied and skip them on subsequent runs.


Implementing Migration Scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``apply()`` and ``undo()`` functions each receive a transaction context (the provider's concrete ``*TransactionContext``, typed as the :class:`~deev.common.DbTransactionContext` protocol) exposing database operations. The migrator wraps each migration in a transaction scope, but **does not commit or roll back on the script's behalf**.

**You must call ``commit()`` explicitly inside every migration function.** If the context manager exits while a transaction is still open — i.e. the script never called ``commit()`` or ``rollback()`` — the context's exit handler rolls the work back and raises a ``DbError``. Likewise, if an exception propagates out of ``apply()`` or ``undo()`` before an explicit commit, the context rolls back on exit.


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

SQLite also implicitly commits before DDL statements — the same concern as MySQL applies here. The :class:`~deev.sqlite.SQLiteTransactionContext` handles this by catching ``sqlite3.OperationalError`` on savepoint release and falling back to a full ``COMMIT`` when DDL has killed all savepoints.

**Parameter syntax:** SQLite uses ``?`` placeholders natively. The deev transaction context automatically translates the normalized ``%?`` syntax to ``?``, so you always write ``%?`` in migrations regardless of provider.


MSSQL
~~~~~

**Transactional DDL.** Unlike MySQL and SQLite, SQL Server supports transactional DDL — ``CREATE``, ``DROP``, ``ALTER`` statements do **not** implicitly commit, so a migration can mix schema and data changes atomically.

* TSQL has no nested transactions. ``deev`` tracks transaction depth and **scrubs** nested ``COMMIT``/``BEGIN`` statements (they become no-ops); only the outermost transaction is real.
* Savepoints use ``SAVE TRANSACTION`` and are tracked in LIFO order; ``ROLLBACK TRANSACTION <name>`` reverts to a specific one.
* **Note:** DDL that is not transactionally safe (e.g. ``ALTER DATABASE``, some index operations) implicitly commits — avoid it mid-migration for the same reasons as MySQL/SQLite.

**Parameter syntax:** ``%?`` translates to ``?`` (mssql-python placeholders).


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


ClickHouse
~~~~~~~~~~

**No transactions.** ClickHouse does not support traditional ACID transactions. The :class:`~deev.clickhouse.ClickHouseTransactionContext` implements the same transaction interface as every other provider, but every transaction-control statement is a **no-op** (depth is tracked for diagnostics only). Write each migration so it is safe to re-run without rollback.

* ``update()``/``delete()`` table-adapter methods issue ``ALTER TABLE ... UPDATE/DELETE`` mutations, which are asynchronous and rewrite data parts — keep them rare.
* ``create_table()`` resolves the engine automatically (explicit arg → ``@entity(engine=...)`` → database engine from ``system.databases`` → ``MergeTree``); on replicated tables, ``sync_replicas()`` is invoked after writes.
* On replicated databases, run ``SYSTEM SYNC DATABASE REPLICA <db>;`` after migrations if replicas must converge immediately (``db-migrate generate`` prints this for you).

**Parameter syntax:** ``%?`` translates to named pyformat parameters.


Migration Data Entity
"""""""""""""""""""""

The ``_migrationdata`` entity differs by provider:

* **SQLite / MySQL / MSSQL** — uses an integer auto-increment primary key.
* **MongoDB / ClickHouse** — uses a UUID primary key, since neither supports ``AUTO_INCREMENT``.


Transaction Behavior Summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following table summarizes the transaction behavior across providers during migration execution:

+-------------------------+---------------------------+---------------------------+---------------------------+---------------------------+---------------------------+
| Aspect                  | MySQL                     | SQLite                    | MSSQL                     | MongoDB                   | ClickHouse                |
+=========================+===========================+===========================+===========================+===========================+===========================+
| DDL auto-commit         | **Yes** — implicit before | **Yes** — implicit before | No — DDL is               | N/A (no DDL)              | N/A (no transactions)     |
|                         | ``CREATE``, ``DROP``,     | ``CREATE``, ``DROP``,     | transactional             |                           |                           |
|                         | ``ALTER``, etc.           | ``ALTER``, etc.           |                           |                           |                           |
+-------------------------+---------------------------+---------------------------+---------------------------+---------------------------+---------------------------+
| Savepoint recovery      | Falls back to full        | Catches                   | Not needed                | N/A                       | N/A                       |
|                         | ``ROLLBACK`` on           | ``OperationalError``;     |                           |                           |                           |
|                         | rollback failure          | falls back to full        |                           |                           |                           |
|                         |                           | ``COMMIT``.               |                           |                           |                           |
+-------------------------+---------------------------+---------------------------+---------------------------+---------------------------+---------------------------+
| Nested transactions     | ``SAVEPOINT TID_<uuid>``  | ``SAVEPOINT TID_<uuid>``  | Nested commits scrubbed;  | NOP — parent handles      | NOP — all transaction     |
|                         |                           |                           | savepoints via            | everything                | operations are no-ops     |
|                         |                           |                           | ``SAVE TRANSACTION``      |                           |                           |
+-------------------------+---------------------------+---------------------------+---------------------------+---------------------------+---------------------------+
| Top-level commit        | ``connection.commit()``   | ``COMMIT``                | ``COMMIT TRANSACTION``    | ``commit_transaction()``  | No-op (nothing to         |
|                         |                           |                           |                           |                           | commit)                   |
+-------------------------+---------------------------+---------------------------+---------------------------+---------------------------+---------------------------+
| Parameter syntax        | Provider-native (via      | ``%?`` -> ``?``           | ``%?`` -> ``?``           | ``%?`` -> filter dict     | ``%?`` -> pyformat        |
|                         | mysql.connector)          | auto-translation          | auto-translation          |                           | parameters                |
+-------------------------+---------------------------+---------------------------+---------------------------+---------------------------+---------------------------+


Best Practices
--------------

1. **Always provide an ``undo()``.** Every migration should be reversible. If you cannot undo a change safely, document why clearly as a comment.
2. **Name migrations for sort order.** Use numeric prefixes (``001_``, ``002_``, ...) or date-based names (``2026-06-15_add_index``) to guarantee ordering.
3. **Keep migrations idempotent.** Where possible, use ``IF NOT EXISTS`` / ``IF EXISTS`` guards so re-running is safe.
4. **Commit explicitly inside every migration function.** The migrator requires the migration script to call ``commit()``; failing to do so will raise a ``DbError`` when the context exits.
5. **Be aware of DDL auto-commit on MySQL and SQLite.** Do not assume DML changes before DDL in the same migration are part of the same atomic transaction — split them into separate migration scripts if atomicity matters.
6. **Use the normalized ``%?`` parameter placeholder** regardless of provider — deev handles the translation internally.
