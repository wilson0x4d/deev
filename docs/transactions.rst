Transactions
============

deev's transaction contexts provide a uniform, provider-agnostic transaction API. Every provider implements the same interface (the :class:`~deev.common.DbTransactionContext` protocol), so code written against the protocol works on all providers: SQLite, MySQL, MSSQL, MongoDB, and ClickHouse.


Starting a Transaction
----------------------

Use :func:`~deev.utils.begin_transaction` (sync) or :func:`~deev.utils.begin_transaction_async` (async). Both accept a connection string (a connection is opened and closed with the scope) or an already-open ``DbContext`` (connection or transaction, e.g. inside a migration script or a ``DbAdapter``):

.. code-block:: python

    from deev.utils import begin_transaction, create_table_adapter

    with begin_transaction(conn_str) as db_transaction:
        table = create_table_adapter(User, db_transaction)
        table.create(User(name='Alice'))
        db_transaction.commit()

**Explicit commit is required.** The context manager never commits on your behalf. If the scope exits with a transaction still open, the context rolls the work back and raises ``DbError``; the same rollback happens when an exception propagates out of the scope before you commit.


Unified API
-----------

All transaction contexts (sync and async) expose the same members:

+---------------------------------+----------------------------------------------------------+
| Member                          | Purpose                                                  |
+=================================+==========================================================+
| ``begin_transaction(n)``        | Begin a (nested) transaction; optional name              |
+---------------------------------+----------------------------------------------------------+
| ``commit()``                    | Commit the current scope.                                |
+---------------------------------+----------------------------------------------------------+
| ``rollback(n=None)``            | Rollback the current scope, or to a named savepoint/txn. |
+---------------------------------+----------------------------------------------------------+
| ``create_savepoint(n)``         | Create a savepoint (auto-named ``TID_<uuid>``            |
|                                 | if omitted).                                             |
+---------------------------------+----------------------------------------------------------+
| ``rollback_savepoint(n)``       | Rollback to a named savepoint, or the most recent one.   |
+---------------------------------+----------------------------------------------------------+
| ``execute(sql, params, raw)``   | Execute SQL; returns a cursor. ``raw=True``              |
|                                 | bypasses transaction preprocessing.                      |
+---------------------------------+----------------------------------------------------------+
| ``execute_script(sql, raw)``    | Execute a multi-statement script.                        |
+---------------------------------+----------------------------------------------------------+
| ``execute_nonquery(...)``       | Execute SQL that returns no rows.                        |
+---------------------------------+----------------------------------------------------------+
| ``execute_reader(...)``         | Generator of result rows.                                |
+---------------------------------+----------------------------------------------------------+
| ``execute_scalar(...)``         | First column of the first row.                           |
+---------------------------------+----------------------------------------------------------+
| ``cursor()``                    | Underlying :class:`~deev.common.DbCursor`.               |
+---------------------------------+----------------------------------------------------------+
| ``connection`` (property)       | Underlying :class:`~deev.common.DbConnection`.           |
+---------------------------------+----------------------------------------------------------+
| ``transaction_name`` (property) | Outermost transaction name, or ``None``.                 |
+---------------------------------+----------------------------------------------------------+
| ``savepoints`` (property)       | Current savepoint names.                                 |
+---------------------------------+----------------------------------------------------------+
| ``close()``                     | Release resources.                                       |
+---------------------------------+----------------------------------------------------------+

SQL always uses the normalized ``%?`` placeholder; each provider translates it to its native syntax at runtime.


Named Transactions and Savepoints
---------------------------------

* ``begin_transaction(name)`` names the outermost transaction; the name is available via the ``transaction_name`` property and can be used with ``rollback(name)``.
* ``create_savepoint(name)`` creates a savepoint (named ``TID_<uuid>`` when omitted) tracked in LIFO order; ``rollback_savepoint(name)`` reverts to that savepoint (or the most recent one when ``name`` is omitted).
* Nested transaction scopes map to savepoints where the DBMS supports them; where it does not (TSQL, MongoDB, ClickHouse), nested operations degrade gracefully — see below.


Behavior by Provider
--------------------

+--------------+--------------------------------------------------------+
| Provider     | Behavior                                               |
+==============+========================================================+
| SQLite       | ``SAVEPOINT``-based nesting. DDL auto-commits          |
|              | (see below); the context falls back to a full          |
|              | ``COMMIT`` when a savepoint release fails              |
|              | because DDL killed it.                                 |
+--------------+--------------------------------------------------------+
| MySQL        | ``SAVEPOINT``-based nesting. DDL auto-commits          |
|              | (see below); savepoints are managed defensively,       |
|              | with fallback to a full ``ROLLBACK``.                  |
+--------------+--------------------------------------------------------+
| MSSQL        | TSQL has no nested transactions: nested                |
|              | ``BEGIN``/``COMMIT`` statements are **scrubbed**       |
|              | (no-ops) and depth is tracked. Savepoints use          |
|              | ``SAVE TRANSACTION``.                                  |
+--------------+--------------------------------------------------------+
| MongoDB      | Real ``pymongo.ClientSession`` transactions at         |
|              | the top level; nested scopes are no-ops (the           |
|              | parent scope commits or aborts). Exposes               |
|              | ``mongo_client``, ``mongo_database``,                  |
|              | ``mongo_session``, ``mongo_database_name``.            |
+--------------+--------------------------------------------------------+
| ClickHouse   | No transactions: every transaction-control             |
|              | statement is a no-op (depth tracked for                |
|              | diagnostics only). Exposes ``clickhouse_client``.      |
+--------------+--------------------------------------------------------+


DDL and Auto-Commit
-------------------

MySQL and SQLite implicitly commit any active transaction before executing DDL statements (``CREATE``, ``DROP``, ``ALTER``, ...). Consequences:

* DML changes made **before** a DDL statement in the same scope are committed early and cannot be rolled back together with later changes.
* Savepoints created before the DDL are released by the implicit commit; the transaction contexts recover by falling back to a full rollback/commit where needed.

**Best practice:** if atomicity matters, split schema changes and data changes into separate migration scripts so the DDL runs in its own clean scope. MSSQL does not have this problem (transactional DDL); MongoDB and ClickHouse have no DDL-transaction interaction at all.
