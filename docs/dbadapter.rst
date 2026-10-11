Database Adapters
=================

When an application talks to several related tables, :class:`~deev.common.DbAdapter` (sync) and :class:`~deev.common.AsyncDbAdapter` (async) give you a class-based database adapter: declare typed table adapter properties for the tables in a single database, and deev wires them up for you.


Defining a DbAdapter
--------------------

Subclass ``DbAdapter``, pass a connection string, and expose one property per table:

.. code-block:: python

    from deev.common import DbAdapter, ConnectionString
    from deev.mongodb import MongoTableAdapter
    from myapp.entities import Document, Attachment


    class MyDbAdapter(DbAdapter):
        def __init__(self, connection_string: ConnectionString | str):
            super().__init__(connection_string)

        @property
        def documents(self) -> MongoTableAdapter[Document]:
            return self.get_table_adapter(Document)

        @property
        def attachments(self) -> MongoTableAdapter[Attachment]:
            return self.get_table_adapter(Attachment, create_table=True)


.. code-block:: python

    with MyDbAdapter(conn_str) as db:
        db.documents.create(Document(title='hello'))
        doc_pk = db.documents.read(id=1)
        tx = db.begin_transaction()


How It Works
------------

* **Auto-discovery** — ``__init_subclass__`` inspects each property's return type hint (``*TableAdapter[Entity]``) and registers the entity.
* ``get_table_adapter(entity_type, create_table=False, table_name=None, **kwargs)`` — lazily creates and caches the provider-appropriate adapter from the open connection (delegating to ``deev.utils`` factories). Provider-specific kwargs (e.g. ``sync_replicas=True`` for ClickHouse) pass straight through.
* **It is also a connection** — ``DbAdapter`` implements ``DbConnection``, so it has ``cursor()``, ``commit()``, ``rollback()``, ``close()``, a ``connection`` property, and ``begin_transaction()``.
* **Context manager** — entering the context calls ``connect()``; the connection is closed on ``__del__``/``close()``.
* **Async variant** — ``AsyncDbAdapter`` works the same way with ``async with`` and awaits: ``await db.documents.create(...)``.

The same property-based introspection powers :func:`~deev.utils.generate_dbadapter_ddl`: it discovers every ``*TableAdapter[Entity]`` property on a ``DbAdapter`` subclass and generates DDL for each referenced entity — which is what ``db-migrate generate database`` uses.
