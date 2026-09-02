---
name: deev
description: deev Python entity framework — define entities with @entity and field(), perform CRUD via TableAdapters, manage migrations with db-migrate CLI. Supports SQLite, MySQL, MongoDB, and ClickHouse. Includes async API. Use as a reference for high-level usage patterns.
user-invocable: true
disable-model-invocation: false
type: reference
---

# deev — AI-First Skill

**deev** is a Python 3.11+ entity framework. It maps Python classes to database tables/collections, provides CRUD via `TableAdapter`s, and includes a `db-migrate` CLI.

**Providers:** `sqlite3` (built-in), `mysql` (`pip install deev[mysql]`), `mongodb` (`pip install deev[mongodb]`), `clickhouse` (`pip install deev[clickhouse]`).

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
| `default` | `Any \| Callable \| None` | Static value or zero-arg callable. Uses sentinel `__NOTSET__` internally to distinguish "not set" from `None`. |
| `index` | `str \| IndexOptions \| None` | Index name or `IndexOptions(name=..., direction=..., rank=..., type=...)`. |
| `init` | `bool` | Whether field participates in `__init__`. Default `True`. |
| `mapped` | `bool \| None` | If `False`, excluded from SQL translation. Default `None`. |
| `max` | `int \| float \| Decimal \| None` | Maximum value or string length. Default `None`. |
| `min` | `int \| float \| Decimal \| None` | Minimum value or string length. Default `None`. |
| `nullable` | `bool \| None` | Allows NULL. Inferred from `Optional[...]`. Default `None`. |
| `primary_key` | `bool \| None` | Part of the primary key. Default `None`. |
| `dbtype` | `str \| None` | Override auto-detected database type. Default `None`. |
| `unique` | `bool \| None` | Unique constraint. Default `None`. |
| `validator` | `Callable[[Any], Any] \| None` | Custom validator. Return `None` to pass. Default `None`. |

### IndexOptions and IndexOrder

```python
from deev.entities import IndexOptions, IndexOrder

IndexOptions(
    name="idx_users_email",
    direction=IndexOrder.ASCENDING,   # or IndexOrder.DESCENDING
    rank=0,
    type=None                          # optional provider-specific index type
)
```

### `@entity` decorator parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `table_name` | `str \| None` | `None` | Override auto-generated table name. |
| `no_pluralization` | `bool` | `False` | Don't pluralize class name for table name. |
| `defer_init` | `bool` | `False` | Call original `__init__` BEFORE field defaults are applied (useful for mixin base classes). |
| `snake_case` | `bool` | `False` | Convert class name to snake_case before pluralizing for table name. |
| `**kwargs` | `Any` | — | Forwarded to `define_entity_spec` (entity spec extra arguments). |

**Entity/table naming:** table name defaults to pluralized class name. Override with `@entity(table_name='...')`, `@entity(no_pluralization=True)`, or `@entity(snake_case=True)`.

---

## 2. Connections

Use `connect()` with a connection string. Returns a context-managed connection:

```python
from deev import connect

conn_str = 'Server=./data/;Database=mydb.db;Provider=sqlite3'
# MySQL:    'Server=localhost;Database=mydb;UID=root;PWD=secret;Provider=mysql'
# MongoDB:  'Server=localhost;Database=mydb;Provider=mongodb'
# ClickHouse: 'Server=localhost;Database=analytics;Provider=clickhouse'

with connect(conn_str, connect_timeout=5, command_timeout=15) as db:
    ...
```

### Connection Strings

Parsed by `deev.ConnectionString`. Supports two formats:

**DSN (URI) format** — automatically mapped to providers:

| DSN Scheme | Provider |
|------------|----------|
| `mysql://` | `mysql.connector` |
| `mysql2://` | `mysql.connector` |
| `sqlite://` | `sqlite` |
| `sqlite3://` | `sqlite3` |
| `mongodb://` | `mongodb` |
| `mongodb+srv://` | `mongodb` |
| `clickhouse://` | `clickhouse` |

Examples:
```python
ConnectionString('mysql://root:pass@127.0.0.1:3306/mydb')
ConnectionString('sqlite3:///path/to/db.sqlite')
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

Recognized keys (case-insensitive): `server`, `database`, `uid`, `user`, `user id`, `username`, `pwd`, `password`, `pass`, `provider`, `connection timeout`, `command timeout`.

**Properties:** `server`, `database`, `user`, `password`, `provider`, `connect_timeout`, `command_timeout`, `parameters` (arbitrary extra params from DSN query string).

```python
from deev import ConnectionString
cs = ConnectionString('Server=localhost;Database=prod;Provider=mysql')
cs.server   # "localhost"
str(cs)     # reconstituted connection string
```

Create the database if missing: `deev.utils.create_database(conn_str)`.

Resolve MongoDB authSource automatically: `deev.utils.resolve_mongodb_auth_source(conn_str)`.

---

## 3. Transactions

Use `begin_transaction()` from `deev.utils` for transactional scopes. **The migration writer must call `tx.commit()` or `tx.rollback()` explicitly inside every migration script.**

```python
from deev.utils import begin_transaction

with begin_transaction(conn_str) as tx:
    table = create_table_adapter(User, tx)
    table.create(User(name="Alice"))
    tx.commit()
```

Raw SQL via `tx.execute(...)`, `tx.execute_scalar(...)`, `tx.execute_nonquery(...)` etc.

### Transaction context types by provider

| Provider | Context class |
|----------|--------------|
| SQLite / MySQL | `DbTransactionContext` |
| MongoDB | `MongoTransactionContext` |
| ClickHouse | `ClickHouseTransactionContext` |

For MongoDB and ClickHouse, migration scripts use their respective context types (see migrations section).

---

## 4. Tables (CRUD)

Create a provider-specific `TableAdapter` for typed CRUD:

```python
from deev.sqlite import SqliteTableAdapter      # or ...mysql.MysqlTableAdapter, ...mongodb.MongoTableAdapter, ...clickhouse.ClickHouseTableAdapter

table = SqliteTableAdapter[User](db)
table.create_table()
```

Or auto-detect: `table = create_table_adapter(User, conn_str)` from `deev.utils`.

### Unified CRUD methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `create_table` | `create_table()` | — |
| `create` | `create(entity, **kwargs)` | `{pk_name: pk_value}` |
| `read` | `read(**pk_kwargs)` | Entity or `None` |
| `update` | `update(entity)` | — |
| `delete` | `delete(**pk_kwargs)` | — |
| `exists` | `exists(**pk_kwargs)` | `bool` |
| `upsert` | `upsert(entity)` | `{pk_name: pk_value}` |
| `query` | `query(where?, params?, orderby?, limit?)` | `Generator[Entity]` |
| `bulk_create` | `bulk_create(entities)` | `list[{pk_name: pk_value}]` |

`bulk_create` is available on ClickHouse adapters only.

### Key provider differences

- **SQLite/MySQL:** tables must be created with `create_table()` (DDL).
- **MongoDB:** collections are created implicitly on first insert — no DDL needed. `create_table()` creates indexes.
- **ClickHouse:** tables require `create_table(engine, order_by, partition_by)` with MergeTree engine options. `update()` and `delete()` are mutations (expensive, rewrite data parts). `bulk_create()` uses native batch insert. `sync_replicas()` forces replica sync.
- **Parameter syntax:** all providers use `%?` placeholders, translated at runtime (SQLite → `?`, MySQL → `%s`).
- **MongoDB:** auto-increment is not available; `_migrationdata` uses UUID PKs. MongoDB adapters expose `mongo_collection` property for advanced operations.

### Translating entities ↔ dicts

- `splat(entity, to_sql=True)` — entity to dict (optionally serialize complex types).
- `hydrate(EntityClass, dict, from_sql=True)` — dict to entity (or hydrate into existing instance).
- `configure_serialization(*, encoder, decoder, serializer, deserializer)` — customize JSON serialization.
- `to_sqlobject(value, hint)` — convert Python value to SQL-storable form.
- `to_bsonobject(value)` — convert Python value to BSON-storable form (MongoDB).
- `to_pyobject(value, hint)` — convert SQL/BSON value back to Python type.
- `deunionize(t)` — unwrap `Optional[T]` to `T`.

Complex types (`list`, `dict`, `set`, `tuple`, `Decimal`, `UUID`, `datetime`, `date`, `time`, `timedelta`, `bytes`, `Enum`) are auto-serialized to JSON.

---

## 5. Async API

All providers have async variants. Use `connect_async()` to create async connections:

```python
from deev.utils import connect_async, create_table_adapter_async, begin_transaction_async

async with connect_async(conn_str) as db:
    table = await create_table_adapter_async(User, db)
    # use table methods (they return coroutines)
```

Async utilities:
- `connect_async(conn_str)` — async DB connection
- `create_table_adapter_async(entity_type, dbcontext)` — async auto-detect adapter
- `begin_transaction_async(dbcontext)` — async transactional scope

Async table adapters delegate to sync adapters via `asyncio.to_thread` (SQLite) or use native async drivers (MySQL, MongoDB, ClickHouse).

Async transaction contexts mirror sync contexts: `AsyncDbTransactionContext`, `AsyncMongoTransactionContext`, `AsyncClickHouseTransactionContext`.

---

## 6. Migration Scripts with `db-migrate` CLI

### CLI usage

```bash
# Apply all pending migrations
db-migrate apply '<conn_str>' ./migrations/mydb/

# Undo last migration
db-migrate undo --stop-at "002_foo" '<conn_str>' ./migrations/mydb/

# Undo all
db-migrate undo '<conn_str>' ./migrations/mydb/

# Use a named connection from config
db-migrate apply my_production

# Generate DDL
db-migrate generate entity myapp.entities.User '<conn_str>'
db-migrate generate database myapp.db_adapter '<conn_str>'
```

### Migration script structure

**For SQLite and MySQL (uses `DbTransactionContext`):**

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
    tx.execute_nonquery('DROP TABLE IF EXISTS Users')
    tx.commit()  # REQUIRED
```

**For MongoDB (uses `MongoTransactionContext`):**

```python
# migrations/001_create_users.py
from deev.common import MongoTransactionContext
from deev.utils import create_table_adapter
from myapp.entities import User

def apply(tx: MongoTransactionContext) -> None:
    # No create_table() needed for MongoDB — collections created on first insert
    table = create_table_adapter(User, tx)
    table.create(User(name="Alice"))
    tx.commit()

def undo(tx: MongoTransactionContext) -> None:
    tx.commit()
```

**For ClickHouse (uses `ClickHouseTransactionContext`):**

```python
# migrations/001_create_events.py
from deev.common import ClickHouseTransactionContext
from deev.utils import create_table_adapter
from myapp.entities import Event

def apply(tx: ClickHouseTransactionContext) -> None:
    table = create_table_adapter(Event, tx)
    table.create_table(engine='MergeTree()', order_by='event_date')
    tx.commit()

def undo(tx: ClickHouseTransactionContext) -> None:
    tx.execute_nonquery('DROP TABLE IF EXISTS Events')
    tx.commit()
```

### Migration conventions

- Files are processed **alphabetically** by filename. Prefix with numbers: `001_`, `002_`, ...
- Applied migrations are tracked in `_migrationdata` (table for SQL, collection for MongoDB/ClickHouse).
- The CLI skips already-applied migrations.
- `--stop-at "migration_name"` halts processing at that file.
- **Always call `tx.commit()`** inside both `apply` and `undo`.
- Named connections are resolved from `appsettings2` config via keys `connectionStrings__{name}` or `connections__{name}`.

---

## Quick Reference

| Import from `deev` | Purpose |
|--------------------|---------|
| `entity`, `field` | Define entities |
| `connect`, `connect_async` | Create DB connection (sync/async) |
| `ConnectionString` | Parse/build connection strings (DSN and OLEDB formats) |
| `DbError` | Exception for DB errors |
| `common.DbTransactionContext` | Transaction context for SQLite/MySQL |
| `common.MongoTransactionContext` | Transaction context for MongoDB |
| `common.ClickHouseTransactionContext` | Transaction context for ClickHouse |
| `common.AsyncDbTransactionContext` | Async transaction context protocol |
| `validation.validate`, `validation.ValidationError` | Entity validation |
| `translation.splat` / `hydrate` | Entity ↔ dict conversion |
| `translation.configure_serialization` | Customize JSON serialization |
| `translation.to_bsonobject` / `to_pyobject` / `to_sqlobject` | Type conversions |
| `translation.deunionize` | Unwrap `Optional[T]` to `T` |
| `utils.create_database` | Create DB if missing |
| `utils.create_table_adapter` | Auto-detect provider, return adapter |
| `utils.create_table_adapter_async` | Async variant |
| `utils.begin_transaction` | Start transactional scope |
| `utils.begin_transaction_async` | Async variant |
| `utils.apply_migrations` / `undo_migrations` | Programmatic migration |
| `utils.generate_entity_ddl` / `generate_dbadapter_ddl` | Generate DDL statements |
| `utils.resolve_mongodb_auth_source` | Auto-resolve MongoDB authSource |
| `entities.IndexOptions` / `IndexOrder` | Index definition options |

Provider adapters:
- Sync: `deev.sqlite.SqliteTableAdapter`, `deev.mysql.MysqlTableAdapter`, `deev.mongodb.MongoTableAdapter`, `deev.clickhouse.ClickHouseTableAdapter`
- Async: `deev.sqlite.AsyncSqliteTableAdapter`, `deev.mysql.AsyncMysqlTableAdapter`, `deev.mongodb.AsyncMongoTableAdapter`, `deev.clickhouse.AsyncClickHouseTableAdapter`
