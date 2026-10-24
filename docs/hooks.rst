Entity Hooks
============
.. _hooks:

Entities can define **entity hooks** as **static methods** on the entity class. An entity hook is a functional hook that plugs into a specific piece of entity logic.

``on_create_table``
-------------

``on_create_table`` is invoked by a table adapter's :meth:`create_table` **when the backing table is
created** — if the table already exists, no DDL is executed and ``on_create_table`` is not called.

.. code-block:: python

    from deev import entity, field

    @entity
    class User:
        id: int = field(autoincrement=True, primary_key=True)
        name: str

        @staticmethod
        def on_create_table(table_adapter):
            # runs only when create_table() actually created the table
            table_adapter.create(name='admin')


* The hook receives the table adapter that created the table (a sync adapter from a sync
  ``create_table()`` call, an async adapter from an async one). The hook implementation is
  responsible for determining the adapter type and calling its methods accordingly (sync
  adapters return values, async adapters return coroutines to ``await``).
* ``on_create_table`` **may be an ``async def``** function. From an async ``create_table()`` the
  coroutine is awaited. From a sync ``create_table()``, the coroutine is scheduled on the
  current thread's running event loop as a task (when one exists) or run to completion in a new
  loop — see :func:`deev.common.async_run`.
* The hook name is recognized by convention (``on_create_table``) and is excluded from field
  introspection; annotating it does **not** turn it into a mapped column.
* Inherited hooks (defined on a base class) are discovered via the MRO.

When the hook runs
------------------

* ``table.create_table()`` — directly, or lazily via the ``create_table=True`` constructor flag
  (the hook fires during the first operation that triggers deferred initialization).
* ``DbAdapter.get_table_adapter(Entity, create_table=True)`` / ``AsyncDbAdapter``.
* ``db-migrate`` migration scripts that call ``create_table()`` — seed data written by the hook
  participates in the migration transaction.

Because the check for "does the table already exist" happens before the DDL, the hook fires at
most once per table. Two processes racing to create the same table may both observe "does not
exist" and both fire the hook; keep hook bodies idempotent if that scenario matters.

A hook that raises after the DDL has succeeded leaves the table in place; a later
``create_table()`` will see the table as pre-existing and will **not** re-invoke the hook.
Re-running a failed hook (e.g. seed data) is the caller's responsibility.

MongoDB note
------------

MongoDB collections are created implicitly on first insert. The ``on_create_table`` hook is invoked
only by an explicit ``create_table()`` call (which also creates indexes); it is not invoked when
a collection is first created implicitly by an insert.
