Async API
=========

Every provider has a complete async variant: connections, cursors, table adapters, and transaction contexts, all ``Async``-prefixed (e.g. ``AsyncSQLiteTableAdapter``, ``AsyncMongoTransactionContext``). The async API mirrors the sync API one-to-one; only the methods become coroutines (or async generators).


Connecting and CRUD
-------------------

Use :func:`~deev.utils.connect_async` to open an async connection and :func:`~deev.utils.create_table_adapter_async` to obtain a provider-appropriate async table adapter:

.. code-block:: python

    from deev import entity, field
    from deev.utils import connect_async, create_table_adapter_async


    @entity
    class User:
        id: int = field(autoincrement=True, primary_key=True)
        name: str = field(max=256)


    async def main() -> None:
        conn_str = 'Server=./data/;Database=mydb.db;Provider=sqlite3'
        async with connect_async(conn_str) as db:
            table = await create_table_adapter_async(User, db)
            await table.create_table()

            # CREATE / READ / UPDATE / DELETE
            pk = await table.create(User(name='Alice'))
            user = await table.read(**pk)
            user.name = 'Alicia'
            await table.update(user)
            await table.delete(**pk)

            # UPSERT + QUERY (query is an async generator)
            await table.upsert(User(name='Bob'))
            async for row in table.query(where='name = %?', parameters=('Bob',)):
                print(row.name)

Table adapter constructors are synchronous — only their methods are async. Provider-specific differences from the sync API (ClickHouse ``bulk_create``, MongoDB ``mongo_collection``, etc.) carry over, with async Mongo adapters exposing an ``AsyncCollection``.


Transactions
------------

Use :func:`~deev.utils.begin_transaction_async` for async transactional scopes. The same rules as sync transactions apply — **explicitly commit or roll back** before the scope exits:

.. code-block:: python

    from deev.utils import begin_transaction_async, create_table_adapter_async

    async with begin_transaction_async(conn_str) as tx:
        table = await create_table_adapter_async(User, tx)
        await table.create(User(name='Alice'))
        await tx.commit()

Async transaction contexts (``AsyncDbTransactionContext`` and its provider subclasses) expose the same members as their sync counterparts — named transactions, savepoints, ``execute*`` methods — as coroutines.


Provider Notes
--------------

* **Async MSSQL** wraps a synchronous ``mssql_python`` connection behind the async interface — calls are offloaded rather than truly asynchronous at the driver level.
* **Async ClickHouse** uses ``clickhouse_connect``'s async client.
* **Async SQLite** wraps the built-in ``sqlite3`` module in an async interface.
