---
name: deev
description: deev Python entity framework — define entities with @entity and field(), perform CRUD via TableAdapters, manage migrations with db-migrate CLI. Supports SQLite, MySQL, and MongoDB. Use as a reference for high-level usage patterns.
user-invocable: true
disable-model-invocation: false
type: reference
---

# deev — AI-First Skill

**deev** is a Python 3.11+ entity framework. It maps Python classes to database tables/collections, provides CRUD via `TableAdapter`s, and includes a `db-migrate` CLI.

**Providers:** `sqlite3` (built-in), `mysql` (`pip install deev[mysql]`), `mongodb` (`pip install deev[mongodb]`).

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

| Parameter | Type | Meaning |
|-----------|------|---------|
| `autoincrement` | `bool` | Auto-incrementing PK. Default `False`. |
| `default` | `Any \| Callable` | Static value or zero-arg callable. |
| `min` / `max` | `int \| float \| Decimal` | Validation bounds (or string length for `str`). |
| `primary_key` | `bool` | Part of the primary key. |
| `nullable` | `bool` | Allows NULL. Inferred from `Optional[...]`. |
| `index` | `str \| IndexOptions` | Index name or `IndexOptions(name=..., direction=..., rank=...)`. |
| `unique` | `bool` | Unique constraint. |
| `validator` | `Callable[[Any], ValidationError \| None]` | Custom validator. Return `None` to pass. |
| `mapped` | `bool` | If `False`, excluded from SQL translation. |
| `dbtype` | `str` | Override auto-detected database type. |

**Entity/table naming:** table name defaults to pluralized class name. Override with `@entity(table_name='...')` or `@entity(no_pluralization=True)`.

---

## 2. Connections

Use `connect()` with a connection-string-style string. Returns a context-managed connection:

```python
from deev import connect

conn_str = 'Server=./data/;Database=mydb.db;Provider=sqlite3'
# MySQL:    'Server=localhost;Database=mydb;UID=root;PWD=secret;Provider=mysql'
# MongoDB:  'Server=localhost;Database=mydb;Provider=mongodb'

with connect(conn_str, connect_timeout=5, command_timeout=15) as db:
    ...
```

### Connection Strings

Parsed by `deev.ConnectionString`. Supported keys:

`Server`, `Database`, `UID`/`User`/`Username`, `PWD`/`Password`/`Pass`, `Provider`, `Connection Timeout`, `Command Timeout`.

```python
from deev import ConnectionString
cs = ConnectionString('Server=localhost;Database=prod;Provider=mysql')
cs.server   # "localhost"
str(cs)     # reconstituted connection string
```

Create the database if missing: `deev.utils.create_database(conn_str)`.

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

For MongoDB, the migration script signature uses `MongoTransactionContext` instead of `DbTransactionContext` (see migrations section).

---

## 4. Tables (CRUD)

Create a provider-specific `TableAdapter` for typed CRUD:

```python
from deev.sqlite import SqliteTableAdapter      # or ...mysql.MysqlTableAdapter, ...mongodb.MongoTableAdapter

table = SqliteTableAdapter[User](db)
table.create_table()
```

Or auto-detect: `table = create_table_adapter(User, conn_str)` from `deev.utils`.

### Unified CRUD methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `create` | `create(entity, **kwargs)` | `{pk_name: pk_value}` |
| `read` | `read(**pk_kwargs)` | Entity or `None` |
| `update` | `update(entity)` | — |
| `delete` | `delete(**pk_kwargs)` | — |
| `exists` | `exists(**pk_kwargs)` | `bool` |
| `upsert` | `upsert(entity)` | `{pk_name: pk_value}` |
| `query` | `query(where?, params?, orderby?, limit?)` | `Generator[Entity]` |

### Key provider differences

- **SQLite/MySQL:** tables must be created with `create_table()` (DDL).
- **MongoDB:** collections are created implicitly on first insert — no DDL needed.
- **Parameter syntax:** all providers use `%?` placeholders, translated at runtime (SQLite → `?`, MySQL → `%s`).
- **MongoDB:** auto-increment is not available; `_migrationdata` uses UUID PKs. MongoDB adapters expose `mongo_session`/`mongo_database` properties for advanced operations.

### Translating entities ↔ dicts

- `splat(entity, to_sql=True)` — entity to dict (optionally serialize complex types).
- `hydrate(EntityClass, dict, from_sql=True)` — dict to entity (or hydrate into existing instance).

Complex types (`list`, `dict`, `set`, `tuple`, `Decimal`, `UUID`, `datetime`, `date`, `time`, `timedelta`, `bytes`) are auto-serialized to JSON.

---

## 5. Migration Scripts with `db-migrate` CLI

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

### Migration conventions

- Files are processed **alphabetically** by filename. Prefix with numbers: `001_`, `002_`, ...
- Applied migrations are tracked in `_migrationdata` (table for SQL, collection for MongoDB).
- The CLI skips already-applied migrations.
- `--stop-at "migration_name"` halts processing at that file.
- **Always call `tx.commit()`** inside both `apply` and `undo`.

---

## Quick Reference

| Import from `deev` | Purpose |
|--------------------|---------|
| `entity`, `field` | Define entities |
| `connect` | Create DB connection (context manager) |
| `ConnectionString` | Parse/build connection strings |
| `DbError` | Exception for DB errors |
| `common.DbTransactionContext` | Transaction context for SQLite/MySQL |
| `common.MongoTransactionContext` | Transaction context for MongoDB |
| `validation.validate` | On-demand entity validation |
| `translation.splat` / `hydrate` | Entity ↔ dict conversion |
| `utils.create_database` | Create DB if missing |
| `utils.create_table_adapter` | Auto-detect provider, return adapter |
| `utils.begin_transaction` | Start transactional scope |

Provider adapters: `deev.sqlite.SqliteTableAdapter`, `deev.mysql.MysqlTableAdapter`, `deev.mongodb.MongoTableAdapter`.
