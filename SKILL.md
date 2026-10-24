---
name: deev
description: deev Python entity framework — define entities with @entity and field(), perform CRUD via TableAdapters, manage migrations with db-migrate CLI. Supports SQLite, MySQL, MSSQL, MongoDB, and ClickHouse. Includes async API. Use as a reference for high-level usage patterns.
user-invocable: true
disable-model-invocation: false
type: reference
---

# deev — AI-First Skill

**deev** is a Python 3.11+ entity framework. It maps Python classes to database tables/collections, provides CRUD via `TableAdapter`s, and includes a `db-migrate` CLI.

**Providers:** `sqlite3` (built-in), `mysql` (`pip install deev[mysql]`), `mssql` (`pip install deev[mssql]`), `mongodb` (`pip install deev[mongodb]`), `clickhouse` (`pip install deev[clickhouse]`).

---

## 1. Entities

Decorate a class with `@entity` and configure fields with `field(...)`:

```python
from datetime import datetime, timezone
from typing import Optional
from deev import entity, field

@entity
class User:
    id: int = field(autoincrement=True, primary_key=True, default=None)
    name: str = field(max=256)
    email: Optional[str] = field(default=None)
    score: Optional[int] = field(default=None, min=0, max=100)
    created: datetime = field(default=lambda: datetime.now(timezone.utc))
```

### Key `field(...)` parameters

All parameters are keyword-only with `None` defaults (except `init`).

| Parameter | Type | Meaning |
|-----------|------|---------|
| `autoincrement` | `bool \| None` | Auto-incrementing PK. Default `None`. |
| `cascade_delete` | `bool \| None` | With `foreign_key`, emit `ON DELETE CASCADE` so deleting a referenced row deletes this row (DDL only). Default `None` (no cascade — must be explicit). |
| `default` | `Any \| Callable \| None` | Static value or zero-arg callable. Uses sentinel `__NOTSET__` internally to distinguish "not set" from `None`. |
| `foreign_key` | `tuple[type, str] \| None` | Foreign-key target as `(target_entity_type, target_field_name)`, e.g. `foreign_key=(Parent, 'id')`. Consumed by DDL generators for DBMSes that support FKs. Default `None`. |
| `index` | `str \| IndexOptions \| Sequence[str \| IndexOptions] \| None` | Index name, `IndexOptions(name=..., direction=..., rank=..., type=..., unique=...)`, or a (mixed) sequence of either. A field may participate in multiple indexes (one `CREATE INDEX` per index name); duplicate names within a field raise `ValueError`. |
| `init` | `bool` | Whether field participates in `__init__`. Default `True`. |
| `mapped` | `bool \| None` | If `False`, excluded from SQL translation. Default `None`. |
| `max` | `int \| float \| Decimal \| None` | Maximum value or string length. Default `None`. |
| `min` | `int \| float \| Decimal \| None` | Minimum value or string length. Default `None`. |
| `nullable` | `bool \| None` | Allows NULL. Inferred from `Optional[...]`. Default `None`. |
| `primary_key` | `bool \| None` | Part of the primary key. Default `None`. |
| `dbtype` | `str \| None` | Override auto-detected database type. Default `None`. |
| `unique` | `bool \| None` | Unique constraint. Default `None`. |
| `validator` | `Callable[[Any], Any] \| None` | Custom validator. Return `ValidationError \| None`. Default `None`. |

### IndexOptions and IndexOrder

```python
from deev.entities import IndexOptions, IndexOrder

IndexOptions(
    name="idx_users_email",
    direction=IndexOrder.ASCENDING,   # or IndexOrder.DESCENDING
    rank=0,
    type=None,                         # ClickHouse skip-index type: minmax, set, bloom_filter, tokenbf_v1, ngrambf_v1, text
    unique=None                        # per-index uniqueness (None defers to the field's unique flag).
)
```

A field participates in one index per `IndexOptions`; to join several, pass a sequence (names may mix with `IndexOptions`):

```python
@entity
class Event:
    id: int = field(primary_key=True, autoincrement=True)
    status: str = field(index=[
        IndexOptions(name='ix_status_created', rank=0),
        'ix_status_only',
    ])
    created: str = field(index=IndexOptions(name='ix_status_created', rank=1))
```

### `@entity` decorator parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `table_name` | `str \| None` | `None` | Override auto-generated table name. |
| `no_pluralization` | `bool` | `False` | Don't pluralize class name for table name. |
| `defer_init` | `bool` | `False` | Call original `__init__` BEFORE field defaults are applied (useful for mixin base classes). |
| `snake_case` | `bool` | `False` | Convert class name to snake_case before pluralizing for table name. |
| `**kwargs` | `Any` | — | Forwarded to `define_entity_spec` and stored in `EntitySpec.extra_args`. |

**Entity/table naming:** table name defaults to pluralized class name. Override with `@entity(table_name='...')`, `@entity(no_pluralization=True)`, or `@entity(snake_case=True)`.

**Provider-specific extra args:** unrecognized `**kwargs` are stored in `EntitySpec.extra_args` and consumed by the active provider's DDL generation. Currently: ClickHouse supports `engine` (e.g. `@entity(engine='ReplacingMergeTree')`), which is used as the table `ENGINE` in generated DDL instead of the database-level engine.

Entity specs (`EntitySpec`, `EntityFieldSpec`) are immutable — after definition, attempts to modify them raise `AttributeError`.

### Foreign Keys

Foreign-key constraints are declared on a field with `foreign_key=(target_entity_type, target_field_name)`. They are consumed **only by DDL generation** for DBMSes that support foreign keys (SQLite, MySQL, MSSQL). MongoDB and ClickHouse ignore them.

```python
@entity
class ExampleEntityOne:
    id: UUID = field(primary_key=True)

@entity
class ExampleEntityTwo:
    id: UUID = field(primary_key=True)
    one_id: UUID = field(foreign_key=(ExampleEntityOne, 'id'))
```

The DDL generators emit a `FOREIGN KEY` table constraint (e.g. `FOREIGN KEY ([one_id]) REFERENCES [ExampleEntityOnes]([id])`). Adding `cascade_delete=True` appends `ON DELETE CASCADE`, so deleting a referenced row also deletes the dependent rows. The default is **no cascade** — cascading must be configured explicitly.

```python
one_id: UUID = field(foreign_key=(ExampleEntityOne, 'id'), cascade_delete=True)
```

`generate_dbadapter_ddl()` orders the emitted tables so that every foreign-key target is created before the table that references it (topological order, alphabetical tie-break). Foreign-key targets that are not themselves direct `DbAdapter` properties are still included, transitively.

### Entity Hooks

Entities can define **entity hooks** as **static methods**. An entity hook is a functional hook that plugs into a specific piece of entity logic:

```python
@entity
class User:
    id: int = field(autoincrement=True, primary_key=True)
    name: str

    @staticmethod
    def on_create_table(table_adapter):
        # invoked only when create_table() actually created the table
        table_adapter.create(name='admin')
```

- Invoked by a table adapter's `create_table()` **when the backing table is created**; if the table already exists, no DDL runs and `on_create_table` is not called.
- The `table_adapter` argument is the adapter that created the table — `DbTableAdapter` (sync call site) or `AsyncDbTableAdapter` (async call site). The hook implementation must determine the object type and call its methods accordingly (async adapter methods return coroutines).
- `on_create_table` **may be `async def`**. From an async `create_table()` the coroutine is awaited. From a sync `create_table()` it is handled by `deev.common.async_run`: scheduled as a task on the current thread's running event loop when one exists, otherwise run to completion via `asyncio.run`.
- The hook name is recognized by convention and excluded from field introspection — annotating it does not create a column. Inherited hooks are found via the MRO.
- Also fires via `create_table=True` (lazy init on first operation), `get_table_adapter(Entity, create_table=True)`, and `db-migrate` scripts that call `create_table()`.
- A hook that raises after the DDL succeeds leaves the table in place; `create_table()` will not re-invoke the hook (the table now exists). Keep hooks idempotent if concurrent creation races matter.
- **MongoDB:** collections are created implicitly on first insert; `on_create_table` is invoked only by an explicit `create_table()` call.

---

## 2. Connections

Use `connect()` with a connection string. Returns a PEP 249 connection usable as a context manager:

```python
from deev import connect

conn_str = 'Server=./data/;Database=mydb.db;Provider=sqlite3'
# MySQL:    'Server=localhost;Database=mydb;UID=root;PWD=secret;Provider=mysql'
# MSSQL:    'Server=localhost:1433;Database=mydb;UID=sa;PWD=secret;Provider=mssql;TrustServerCertificate=yes'
# MongoDB:  'Server=localhost;Database=mydb;Provider=mongodb'
# ClickHouse: 'Server=localhost;Database=analytics;Provider=clickhouse'

with connect(conn_str, connect_timeout=5, command_timeout=15) as db:
    ...
```

Defaults: `connect_timeout=3`, `command_timeout=9` (overridable via the connection string itself, which takes precedence).

### Connection Strings

Parsed by `deev.ConnectionString`. Supports two formats:

**DSN (URI) format** — automatically mapped to providers:

| DSN Scheme | Provider |
|------------|----------|
| `mysql://` | `mysql.connector` |
| `mysql2://` | `mysql.connector` |
| `sqlite://` | `sqlite` |
| `sqlite3://` | `sqlite3` |
| `mssql://` | `mssql` |
| `mongodb://` | `mongodb` |
| `mongodb+srv://` | `mongodb` |
| `clickhouse://` | `clickhouse` |

Examples:
```python
ConnectionString('mysql://root:pass@127.0.0.1:3306/mydb')
ConnectionString('sqlite3:///path/to/db.sqlite')
ConnectionString('mssql://sa:pass@sql.local:1433/mydb')
ConnectionString('mongodb://user:pass@mongo.local:27017/mydb')
ConnectionString('clickhouse://default:pass@ch.local:8123/analytics')
```

DSN query parameters `connect_timeout` and `command_timeout` are supported:
```python
ConnectionString('mysql://user:pass@localhost:3306/db?connect_timeout=10&command_timeout=30')
```

**OLEDB / key-value format** — semicolon-delimited `Key=Value` pairs:

```python
ConnectionString('Server=127.0.0.1;Database=mydb;UID=root;PWD=pass;Provider=mysql.connector')
```

Recognized keys (case-insensitive): `server`, `data source`, `database`, `catalog`, `uid`, `user`, `user id`, `username`, `pwd`, `password`, `pass`, `provider`, `connection timeout`, `command timeout`. Any other key (e.g. `TrustServerCertificate`, `Encrypt`, `compress`, `access_token`, `cluster`, `engine`) is preserved in `parameters` and passed through to the provider driver.

**Properties:** `server`, `database`, `user`, `password`, `provider`, `connect_timeout`, `command_timeout`, `parameters` (all parsed connection string components plus any extra DSN query parameters, as a `dict[str, str]`). Also `to_parameters()` returns the same dict. All properties have setters.

```python
from deev import ConnectionString
cs = ConnectionString('Server=localhost;Database=prod;Provider=mysql')
cs.server   # "localhost"
str(cs)     # reconstituted OLEDB-style connection string
```

Create the database if missing: `deev.utils.create_database(conn_str)` (also initializes `_migrationdata` for MongoDB).
Drop the database: `deev.utils.drop_database(conn_str, cluster=None)` (`cluster` for ClickHouse `ON CLUSTER` drops).

Resolve MongoDB authSource automatically: `deev.utils.resolve_mongodb_auth_source(conn_str)` (tries target database, then `admin`; caches results).

---

## 3. Transactions

Use `begin_transaction()` from `deev.utils` for transactional scopes. **Migration scripts must call `tx.commit()` (or `tx.rollback()`) explicitly; exiting the context with an open transaction raises `DbError`.**

```python
from deev.utils import begin_transaction

with begin_transaction(conn_str) as tx:
    table = create_table_adapter(User, tx)
    table.create(User(name="Alice"))
    tx.commit()
```

`begin_transaction()` accepts a connection string or an already-open `DbContext` (connection or transaction).

### Unified transaction API (all providers)

| Member | Signature | Purpose |
|--------|-----------|---------|
| `begin_transaction` | `begin_transaction(name=None)` | Begin (nested) transaction. Name optional; outermost name tracks the txn. |
| `commit` | `commit()` | Commit current scope (nested commit is a no-op where the DBMS has no nested transactions). |
| `rollback` | `rollback(name=None)` | Rollback current scope, or to a named savepoint/transaction. |
| `create_savepoint` | `create_savepoint(name=None)` | Create a savepoint (auto-named `TID_<uuid>` if omitted). |
| `rollback_savepoint` | `rollback_savepoint(name=None)` | Rollback to named savepoint, or the most recent one. |
| `execute` | `execute(sql, parameters=None, raw=False)` | Execute SQL; returns a cursor. `raw=True` bypasses transaction preprocessing. |
| `execute_script` | `execute_script(sql, raw=False)` | Execute a multi-statement script. |
| `execute_nonquery` | `execute_nonquery(sql, parameters=None)` | Execute SQL returning no rows. |
| `execute_reader` | `execute_reader(sql, parameters=None)` | Generator of result rows. |
| `execute_scalar` | `execute_scalar(sql, parameters=None)` | First column of first row. |
| `cursor` | `cursor()` | Underlying `DbCursor`. |
| `connection` | property | Underlying `DbConnection`. |
| `transaction_name` | property | Outermost transaction name (or `None`). |
| `savepoints` | property | Current savepoint names. |
| `close` | `close()` | Release resources. |

**Parameter syntax:** all providers use the normalized `%?` placeholder, translated at runtime (SQLite → `?`, MySQL → `%s`, MSSQL → `?`, ClickHouse → pyformat, MongoDB → filter dict).

### Transaction context types by provider

| Provider | Context class | Notes |
|----------|--------------|-------|
| SQLite | `SQLiteTransactionContext` | DDL auto-commits; savepoint fallback to full commit after DDL. |
| MySQL | `MySQLTransactionContext` | DDL auto-commits; savepoints managed defensively. |
| MSSQL | `MSSQLTransactionContext` | Nested commits at depth > 1 are scrubbed to no-ops (TSQL has no nested transactions). |
| MongoDB | `MongoTransactionContext` | Nested txn ops are no-ops (only top-level ambient txn matters). Exposes `mongo_client`, `mongo_database`, `mongo_session`, `mongo_database_name`. |
| ClickHouse | `ClickHouseTransactionContext` | Exposes `clickhouse_client`. |

---

## 4. Tables (CRUD)

Create a provider-specific `TableAdapter` for typed CRUD:

```python
from deev.sqlite import SQLiteTableAdapter      # or deev.mysql.MySQLTableAdapter, deev.mssql.MSSQLTableAdapter, deev.mongodb.MongoTableAdapter, deev.clickhouse.ClickHouseTableAdapter

table = SQLiteTableAdapter[User](db)            # instantiate via the generic alias
table = SQLiteTableAdapter[User](db, create_table=True, table_name='custom_name')
table.create_table()
```

Constructor kwargs: `create_table: bool = False` (auto-create table/collection/indexes on first operation), `table_name: str | None = None` (override), plus provider-specific kwargs (ClickHouse: `sync_replicas: bool = False`).

Or auto-detect: `table = create_table_adapter(User, db_or_conn_str, create_table=False, table_name=None, **kwargs)` from `deev.utils`. Accepts an open `DbContext` (no new connection is opened) or a connection string.

### Unified CRUD methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `create_table` | `create_table()` (ClickHouse: `create_table(engine=None, order_by=None, partition_by=None)`) | — |
| `create` | `create(entity=None, **kwargs)` | `{pk_name: pk_value}` |
| `read` | `read(**pk_kwargs)` | Entity or `None` |
| `update` | `update(entity)` | — |
| `delete` | `delete(**pk_kwargs)` | — |
| `exists` | `exists(**pk_kwargs)` | `bool` |
| `upsert` | `upsert(entity)` | `{pk_name: pk_value}` |
| `query` | `query(where=None, parameters=None, orderby=None, limit=None)` | `Generator[Entity]` |
| `bulk_create` | `bulk_create(entities)` | `list[{pk_name: pk_value}]` |
| `commit` | `commit()` | — |
| `rollback` | `rollback()` | — |
| `primary_key` | property | `tuple[str, ...]` |

`bulk_create` is available on ClickHouse adapters only (native columnar batch insert).

### Key provider differences

- **SQLite/MySQL:** tables must be created with `create_table()` (DDL) or `create_table=True`.
- **MSSQL:** UUIDs stored as hyphenated strings (`UNIQUEIDENTIFIER`); autoincrement PKs use `OUTPUT INSERTED`. Extra OLEDB keys (e.g. `TrustServerCertificate`, `Encrypt`) are passed through to `mssql_python`. The datetime column type is `DEEV__MSSQL__DATETIME_TYPE` (default `DATETIMEOFFSET`, used verbatim; other types switch reads/writes to UTC normalization — see the datetime policy above).
- **MongoDB:** collections are created implicitly on first insert — no DDL needed. `create_table()` creates indexes. The `query()` WHERE clause supports `=`, `!=`/`<>`, `<`, `<=`, `>`, `>=`, `IN (...)`, `IS [NOT] NULL`, combined with `AND`/`OR`. Adapters expose a `mongo_collection` property for advanced operations; transaction contexts expose `mongo_client`, `mongo_database`, `mongo_session`.
- **ClickHouse:** `create_table(engine=None, order_by=None, partition_by=None)` — engine resolution order: explicit `engine` arg → `@entity(engine=...)` extra arg → database engine from `system.databases` (Replicated → ReplicatedMergeTree, else MergeTree) → `MergeTree`. `update()` and `delete()` are mutations (asynchronous, rewrite data parts — expensive). `bulk_create()` uses native columnar insert. `sync_replicas()` forces replica sync (also applied automatically after writes when enabled). Adapters expose a `clickhouse_client` property.
- **Parameter syntax:** all providers use `%?` placeholders, translated at runtime (SQLite → `?`, MySQL → `%s`, MSSQL → `?`).

### Translating entities ↔ dicts

- `splat(entity, attrs=None, to_sql=False, to_bson=False, to_mssql=False, to_mysql=False, to_chsql=False)` — extract field values from entity. Optionally filter to specific attributes (`attrs`) or serialize for a specific storage format (only one mapping flag at a time).
- `hydrate(entity_or_type, data, attrs=None, from_sql=False, from_mssql=False, from_bson=False, from_mysql=False, from_chsql=False)` — dict to entity (or hydrate an existing instance in place; only one mapping flag at a time).
- `configure_serialization(*, encoder, decoder, serializer, deserializer)` — customize JSON serialization.
- `to_sqlobject(value, hint)` — convert Python value to SQLite-storable form.
- `to_mysql_object(value, hint)` / `to_chsql_object(value, hint)` — convert Python value to MySQL- / ClickHouse-storable form (datetimes normalized to UTC).
- `to_mssql_object(value, hint)` — convert Python value to SQL Server-storable form (UUID → hyphenated string, unlike hex in `to_sqlobject`; datetime policy per `DEEV__MSSQL__DATETIME_TYPE`).
- `to_bsonobject(value, hint=None)` — convert Python value to BSON-storable form (MongoDB).
- `to_pyobject(value, hint, *, from_sql, from_mssql, from_bson, from_mysql, from_chsql)` — convert a stored value back to Python type; the `from_*` flags select the datetime read policy.
- `deunionize(t)` — unwrap `Union[T, None]`/`Optional[T]` to `T` (returns input unchanged if not a Union type).

Complex types (`list`, `dict`, `set`, `tuple`, `Decimal`, `UUID`, `datetime`, `date`, `time`, `timedelta`, `bytes`, `Enum`) are auto-serialized to JSON, with recursive element-hint conversion for containers like `list[date]`.

### Datetime timezone policy

Every `datetime` that passes through a deev read or write path is returned/stored **timezone-aware**. The policy has two uniform rules (applied identically on reads and writes):

1. **Naive datetimes are always treated as UTC** — tagged via `replace(tzinfo=utc)`, never interpreted as local time, on any provider.
2. **Aware datetimes keep their offset when the store can carry one** (SQLite, MSSQL `DATETIMEOFFSET`, deev JSON) **and are normalized to UTC** (`astimezone`) when it cannot (MySQL, ClickHouse, MongoDB, MSSQL with any other configured type).

MSSQL's datetime column type is configurable via `DEEV__MSSQL__DATETIME_TYPE` (used **verbatim** in DDL, no validation; default `DATETIMEOFFSET`; e.g. set `DATETIME2(6)` for precision). The configured type selects which side of the policy applies:

| Backend | Write (aware / naive) | Read |
|---------|-----------------------|------|
| SQLite | passes through / tagged UTC (offset stored) | aware as-is; naive → tagged UTC |
| MSSQL (`DATETIMEOFFSET`, default) | passes through / tagged UTC | aware as-is; naive → tagged UTC |
| MSSQL (other `DEEV__MSSQL__DATETIME_TYPE`) | → UTC / tagged UTC | → UTC |
| MySQL, ClickHouse, MongoDB | → UTC (`astimezone`) / tagged UTC | → UTC |
| JSON (flagless splat/encoder/decoder) | as-is (ISO-8601 with offset, `Z` for UTC) / tagged UTC | aware as-is; naive → tagged UTC |

The MSSQL datetime type is resolved from configuration once per process and cached. Full details: `docs/datetime.rst`.

---

## 5. Database Adapters (`DbAdapter` / `AsyncDbAdapter`)

For applications with multiple related tables, subclass `DbAdapter` (sync) or `AsyncDbAdapter` (async) and declare typed table adapter properties. Note: this is unrelated to the `DbContext` type alias (a connection-or-transaction context) — `DbAdapter` is the class-based adapter that groups table adapters for a single database:

```python
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

with MyDbAdapter(conn_str) as db:
    db.documents.create(Document(title='hello'))
    tx = db.begin_transaction()
```

- Properties returning `*TableAdapter[Entity]` are auto-discovered (`__init_subclass__`); `get_table_adapter(Entity, create_table=False, table_name=None, **kwargs)` lazily creates and caches adapters.
- `DbAdapter` is also a `DbConnection`: it has `cursor()`, `commit()`, `rollback()`, `close()`, `begin_transaction()`, and a `connection` property.
- `generate_dbadapter_ddl()` introspects these properties to generate DDL for all referenced entities.

---

## 6. Async API

All providers have async variants. Use `connect_async()` from `deev.utils`:

```python
from deev.utils import connect_async, create_table_adapter_async, begin_transaction_async

async with connect_async(conn_str) as db:
    table = await create_table_adapter_async(User, db)
    # table methods return coroutines
```

Async utilities:
- `connect_async(conn_str, connect_timeout=3, command_timeout=9, **kwargs)` — async DB connection
- `create_table_adapter_async(entity_type, dbcontext, create_table=False, table_name=None, **kwargs)` — async auto-detect adapter
- `async_db_table_adapter_factory(entity_type, dbcontext, ...)` — sync factory for async adapters (constructors are sync; methods are async)
- `begin_transaction_async(dbcontext_or_conn_str)` — async transactional scope

Async transaction contexts mirror sync contexts: `AsyncDbTransactionContext`, `AsyncSQLiteTransactionContext`, `AsyncMySQLTransactionContext`, `AsyncMSSQLTransactionContext`, `AsyncMongoTransactionContext`, `AsyncClickHouseTransactionContext`.

Note: async MSSQL wraps a synchronous `mssql_python` connection exposed through an async interface.

---

## 7. Migration Scripts with `db-migrate` CLI

### CLI usage

```bash
# Apply all pending migrations ("all" = process everything)
db-migrate apply all '<conn_str>' ./migrations/mydb/

# Apply up to and including a specific migration
db-migrate apply 002_add_email '<conn_str>' ./migrations/mydb/

# Undo all applied migrations (reverse order)
db-migrate undo all '<conn_str>' ./migrations/mydb/

# Undo down to and including a specific migration
db-migrate undo 001_create_users '<conn_str>' ./migrations/mydb/

# Use a named connection from appsettings2 config
db-migrate apply all my_production

# Path is optional — defaults to ./migrations/{database_name}/
db-migrate apply all '<conn_str>'

# Verbose logging
db-migrate --verbose apply all '<conn_str>'

# Generate DDL (alpha-quality)
db-migrate generate entity myapp.entities.User '<conn_str>'
db-migrate generate database myapp.db_adapter '<conn_str>'
```

- `connection` is a literal connection string (contains `=`) or a named connection resolved from `appsettings2` config via keys `connectionStrings__{name}` or `connections__{name}`.
- `generate` prints each DDL statement (plus `USE {database};`, and `SYSTEM SYNC DATABASE REPLICA {db};` for ClickHouse replicated databases).

### Migration script structure

Migration scripts are plain Python files defining `apply(tx)` and `undo(tx)`, each receiving the provider's transaction context (type as the protocol `DbTransactionContext` or the concrete context class):

```python
# migrations/001_create_users.py
from deev.common import DbTransactionContext
from deev.utils import create_table_adapter
from myapp.entities import User

def apply(tx: DbTransactionContext) -> None:
    table = create_table_adapter(User, tx)
    table.create_table()
    tx.commit()  # REQUIRED

def undo(tx: DbTransactionContext) -> None:
    tx.execute_nonquery('DROP TABLE IF EXISTS `Users`')
    tx.commit()  # REQUIRED
```

For MongoDB the context is `MongoTransactionContext` (collections created on first insert; no `create_table()` DDL needed), and for ClickHouse it is `ClickHouseTransactionContext` (`create_table(engine='MergeTree()', order_by='event_date')`).

### Migration conventions

- Files are processed **alphabetically** by filename (reverse for undo). Prefix with numbers: `001_`, `002_`, ...
- Applied migrations are tracked in `_migrationdata` (table for SQL providers, collection for MongoDB/ClickHouse). SQL providers use an integer auto-increment PK; MongoDB/ClickHouse use a UUID PK (no autoincrement support).
- The migrator skips already-applied migrations and requires each script to define both `apply(...)` and `undo(...)` (missing `apply` raises `DbError`).
- **Always call `tx.commit()`** inside both `apply` and `undo`; the migrator does not commit for you.
- **DDL auto-commit:** MySQL and SQLite implicitly commit before DDL statements — savepoints are managed defensively, but DML before DDL in the same script may be committed early. Split DDL and data changes into separate scripts if atomicity matters.
- Programmatic access: `deev.utils.apply_migrations(name, connectionstring, migrations_path=None)` / `undo_migrations(...)` (`migrations_path` defaults to `./migrations/{database}/`), or `deev.common.DbMigrator(connectionstring).apply(path, stop_at)` / `.undo(path, stop_at)`.

---

## Quick Reference

| Import from `deev` | Purpose |
|--------------------|---------|
| `entity`, `field` | Define entities |
| `connect` | Create sync DB connection (PEP 249) |
| `hydrate`, `splat` | Entity ↔ dict translation |
| `ConnectionString` | Parse/build connection strings (DSN and OLEDB formats) |
| `DbError` | Exception for DB errors |
| `common` | Common base types and protocols module |
| `entities` | Entity definitions module |
| `translation` | Serialization/hydration module |
| `utils` | Utility functions module (`connect_async` lives here, not top-level) |
| `validation` | Validation utilities module |
| `sqlite` | SQLite provider module |
| `mysql` | MySQL provider module |
| `mongodb` | MongoDB provider module |
| `clickhouse` | ClickHouse provider module |

Note: `deev.mssql` is a provider submodule (import via `import deev.mssql`).

### From `deev.common`

| Name | Purpose |
|------|---------|
| `DbAdapter` | Sync database adapter base (typed table adapter properties, `get_table_adapter`) |
| `AsyncDbAdapter` | Async database adapter base |
| `DbConnection` | Sync DB connection interface |
| `AsyncDbConnection` | Async DB connection interface |
| `DbCursor` | Sync cursor interface |
| `AsyncDbCursor` | Async cursor interface |
| `DbTableAdapter` | Sync table adapter protocol |
| `AsyncDbTableAdapter` | Async table adapter protocol |
| `DbTransactionContext` | Sync transaction context protocol |
| `AsyncDbTransactionContext` | Async transaction context protocol |
| `DbContext` / `AsyncDbContext` | Type aliases: connection-or-transaction contexts |
| `DbMigrator` | Migration engine (`apply(path, stop_at)`, `undo(path, stop_at)`) |
| `DbParameters` | Parameter binding |
| `DbTypeMapper` | Python-to-DB type mapping base |
| `ConnectionString` | Connection string parser/builder |
| `DbError` | Exception for DB errors |

### From `deev.entities`

| Name | Purpose |
|------|---------|
| `entity` | Entity class decorator |
| `field` | Field spec factory |
| `EntitySpec` | Full specification of an entity class (frozen; includes `extra_args`) |
| `EntityFieldSpec` | Specification for a single entity field (frozen) |
| `IndexOptions` | Options for defining indexes (frozen dataclass) |
| `IndexOrder` | Direction for index ordering (ASC/DESC) |
| `define_entity_spec` | Define/retrieve a custom entity spec |
| `get_entity_spec` | Retrieve spec for a class (creates if missing) |
| `ON_CREATE_TABLE` | Hook name constant (`'on_create_table'`) |
| `get_on_create_table_hook` | Retrieve the `on_create_table` hook for an entity type (`None` if absent) |
| `invoke_on_create_table` / `invoke_on_create_table_async` | Internal hook invocation (sync / async call sites) |
| `pluralize` | Utility to pluralize table names |

### From `deev.translation`

| Name | Purpose |
|------|---------|
| `splat` | Extract entity field values (parameters: `attrs`, `to_sql`, `to_bson`, `to_mssql`, `to_mysql`, `to_chsql`) |
| `hydrate` | Create/hydrate entity instances from dicts (parameters: `attrs`, `from_sql`, `from_mssql`, `from_bson`, `from_mysql`, `from_chsql`) |
| `configure_serialization` | Customize JSON serialization |
| `DeevJsonEncoder` | Custom JSON encoder for deev types |
| `DeevJsonDecoder` | Custom JSON decoder for deev types |
| `to_sqlobject` | Convert Python value to SQLite-storable form |
| `to_mysql_object` | Convert Python value to MySQL-storable form (datetime → UTC) |
| `to_chsql_object` | Convert Python value to ClickHouse-storable form (datetime → UTC) |
| `to_mssql_object` | Convert Python value to SQL Server-storable form (datetime policy per `DEEV__MSSQL__DATETIME_TYPE`) |
| `to_bsonobject` | Convert Python value to BSON-storable form |
| `to_pyobject` | Convert stored value back to Python type (parameters: `from_sql`, `from_mssql`, `from_bson`, `from_mysql`, `from_chsql`) |
 | `get_mssql_datetime_type` | Configured MSSQL datetime type, verbatim (process-cached; default `DATETIMEOFFSET`) |
 | `MSSQL_DATETIME_TYPE_CONFIG_KEY` | Name of the `DEEV__MSSQL__DATETIME_TYPE` configuration setting |
| `deunionize` | Unwrap `Union[T, None]` to `T` |

### From `deev.validation`

| Name | Purpose |
|------|---------|
| `validate` | Validate entity instance (parameters: `attrs`); returns `list[ValidationError] \| None` |
| `ValidationError` | Exception/value representing a validation failure |

### From `deev.utils`

| Name | Purpose |
|------|---------|
| `connect` / `connect_async` | Create sync/async DB connection |
| `create_database` | Create DB if missing (+ init `_migrationdata` for MongoDB) |
| `drop_database` | Drop a DB (supports ClickHouse `cluster`) |
| `create_table_adapter` / `create_table_adapter_async` | Auto-detect provider, return sync/async table adapter |
| `db_table_adapter_factory` / `async_db_table_adapter_factory` | Create sync/async table adapter for entity + open context |
| `begin_transaction` / `begin_transaction_async` | Start sync/async transactional scope |
| `apply_migrations` / `undo_migrations` | Programmatic migration |
| `generate_entity_ddl` / `generate_dbadapter_ddl` | Generate DDL statements (MongoDB entity DDL: `NotImplementedError`) |
| `resolve_mongodb_auth_source` | Auto-resolve MongoDB authSource |

### Provider module exports

Each provider module exports the following classes (sync + async variants; `Async` prefix for async):

| Component | SQLite | MySQL | MSSQL | MongoDB | ClickHouse |
|-----------|--------|-------|-------|---------|------------|
| Connection | `SQLiteProxyConnection` | `MySQLProxyConnection` | `MSSQLProxyConnection` | `MongoProxyConnection` | `ClickHouseProxyConnection` |
| Cursor | `SQLiteProxyCursor` | `MySQLProxyCursor` | `MSSQLProxyCursor` | `MongoProxyCursor` | `ClickHouseProxyCursor` |
| TableAdapter | `SQLiteTableAdapter` | `MySQLTableAdapter` | `MSSQLTableAdapter` | `MongoTableAdapter` | `ClickHouseTableAdapter` |
| Transaction | `SQLiteTransactionContext` | `MySQLTransactionContext` | `MSSQLTransactionContext` | `MongoTransactionContext` | `ClickHouseTransactionContext` |
| DDL Generator | `SQLiteDDLGenerator` | `MySQLDDLGenerator` | `MSSQLDDLGenerator` | — | `ClickHouseDDLGenerator` |
| Type Mapper | `SQLiteTypeMapper` | `MySQLTypeMapper` | `MSSQLTypeMapper` | `MongoTypeMapper` | `ClickHouseTypeMapper` |
