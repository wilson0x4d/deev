Python ``datetime`` Handling
============================

deev normalizes ``datetime`` values on every read and write path so that the value your code sees is always **timezone-aware**.  The policy is uniform and predictable regardless of the provider, and it preserves the instants written by any deev version.  This page describes the behavior at the deev, driver, and database layers.


The Policy
----------

The policy has exactly two rules, applied identically on reads and writes:

1. A naive ``datetime`` is always treated as UTC.  It is tagged with ``timezone.utc`` via ``replace`` — the wall time is the UTC wall time, and the instant is never shifted.  Naive values are *never* interpreted as local time, on any provider.
2. A timezone-aware ``datetime`` keeps its offset when the store can carry one, and is normalized to UTC when the store cannot.  If the store supports offset storage (SQLite, MSSQL ``DATETIMEOFFSET``, and deev's JSON encoding), the value passes through unchanged.  Otherwise (MySQL, ClickHouse, MongoDB), it is converted to UTC via ``astimezone``.


Provider Behavior
-----------------

SQLite
~~~~~~

- **Database:** the column type is ``DATETIME``; deev registers an explicit ``sqlite3`` adapter that stores the value as an ISO-8601 string (space-separated) **with its offset**, so offsets are preserved in the database.
- **Driver:** the stdlib ``sqlite3`` module has no offset support of its own; the adapter above is what carries the offset.
- **deev policy (write and read):** aware values pass through unchanged; naive values are tagged UTC.

MySQL
~~~~~

- **Database:** the column type is ``DATETIME(6)``; it cannot store an offset, so deev stores **UTC**.
- **Driver:** ``mysql.connector`` drops ``tzinfo`` when binding (it sends the wall time) and returns naive ``datetime`` values on reads.
- **deev policy (write and read):** aware values are converted to UTC; naive values are tagged UTC.  On reads, the stored wall time (UTC) is tagged UTC.

ClickHouse
~~~~~~~~~~

- **Database:** the column type is ``DateTime64(6)``; plain ``DateTime64`` cannot store an offset, so deev stores **UTC**.
- **Driver:** ``clickhouse_connect`` drops offset information for plain ``DateTime64`` columns and returns naive ``datetime`` values on reads.
- **deev policy (write and read):** identical to MySQL.

MSSQL
~~~~~

- **Database:** the column type is ``DEEV__MSSQL__DATETIME_TYPE`` (default ``DATETIMEOFFSET``; any other value is used verbatim).  ``DATETIMEOFFSET`` stores the offset; ``DATETIME``/``DATETIME2`` do not (values are stored as UTC).
- **Driver:** ``mssql_python`` binds aware datetimes as ``SQL_DATETIMEOFFSET`` and naive datetimes as ``SQL_TYPE_TIMESTAMP``; it returns aware values for ``DATETIMEOFFSET`` columns and naive values for ``DATETIME``/``DATETIME2`` columns.
- **deev policy (write and read):** see the ``DEEV__MSSQL__DATETIME_TYPE`` table above.


The ``DEEV__MSSQL__DATETIME_TYPE`` Setting
++++++++++++++++++++++++++++++++++++++++++

Allows overriding the SQL Server type used for ``datetime`` fields.  For example, if you have a legacy system that uses ``DATETIME2`` or ``DATETIME`` and want to use deev.  When the key is absent, ``DATETIMEOFFSET`` is the default.  The value is read from configuration once and cached for the lifetime of the process.

The configured type selects which side of the policy applies to MSSQL:

+--------------------------+--------------------------------------------------+--------------------------------------------------+
| Value                    | Store                                            | deev policy                                      |
+==========================+==================================================+==================================================+
| ``DATETIMEOFFSET``       | Can carry the offset                             | aware: unchanged (offset stored);                |
| (default)                |                                                  | naive: tagged UTC                                |
+--------------------------+--------------------------------------------------+--------------------------------------------------+
| anything else (e.g.      | Cannot carry the offset — stores UTC             | aware: converted to UTC;                         |
| ``DATETIME``,            |                                                  | naive: tagged UTC                                |
| ``DATETIME2(6)``)        |                                                  |                                                  |
+--------------------------+--------------------------------------------------+--------------------------------------------------+




MongoDB
~~~~~~~

- **Database:** BSON ``datetime`` is a millisecond count since the Unix epoch — always a UTC instant; there is no offset concept.
- **Driver:** PyMongo (deev connects without ``tz_aware``), so values come back naive, representing the UTC instant.
- **deev policy (write and read):** aware values are converted to UTC; naive values are tagged UTC.  On reads, the stored instant is tagged UTC.

JSON (deev's own encoding)
~~~~~~~~~~~~~~~~~~~~~~~~~~

The flagless ``splat``/``hydrate`` path and ``DeevJsonEncoder``/``DeevJsonDecoder`` serialize datetimes as ISO-8601 strings: UTC uses the ``Z`` suffix, other zones use their numeric offset (e.g. ``+05:00``).  The JSON encoding can carry an offset, so the policy is: aware values pass through unchanged (offset preserved); naive values are tagged UTC.


Comparison
----------

+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| Provider      | deev column type      | Stores offset?      | Write (aware / naive)           | Read (stored value → Python)     |
+===============+=======================+=====================+=================================+==================================+
| SQLite        | ``DATETIME``          | yes (in the text)   | unchanged / tagged UTC          | aware unchanged /                |
|               | (ISO-8601 text)       |                     |                                 | naive → tagged UTC               |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| MySQL         | ``DATETIME(6)``       | no                  | UTC / tagged UTC                | → UTC                            |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| ClickHouse    | ``DateTime64(6)``     | no                  | UTC / tagged UTC                | → UTC                            |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| MSSQL         | ``DATETIMEOFFSET``    | yes                 | unchanged / tagged UTC          | aware unchanged /                |
| (default)     |                       |                     |                                 | naive → tagged UTC               |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| MSSQL         | verbatim (e.g.        | no                  | UTC / tagged UTC                | → UTC                            |
| (configured)  | ``DATETIME2(6)``)     |                     |                                 |                                  |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| MongoDB       | BSON datetime         | n/a (UTC instant)   | UTC / tagged UTC                | → UTC                            |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+
| JSON          | ISO-8601 string       | yes (offset/``Z``)  | unchanged / tagged UTC          | aware unchanged /                |
|               |                       |                     |                                 | naive → tagged UTC               |
+---------------+-----------------------+---------------------+---------------------------------+----------------------------------+

.. note::
   "tagged UTC" means the wall time is unchanged and ``timezone.utc`` is applied via ``replace``; "→ UTC" means the stored value is the UTC wall time and is returned to your code tagged with ``timezone.utc``.


Related Utility Functions
-------------------------

.. automodule:: deev.translation.datetime_utils
   :members:
   :undoc-members:
   :show-inheritance:
