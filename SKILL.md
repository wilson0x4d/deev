---
name: deev
description: deev Python entity framework — define entities with @entity and field(), perform CRUD via TableAdapter, translate between entity/dict/SQL via splat()/hydrate(), validate entities, manage migrations. Use when working with deev entities, table adapters, connection strings, or db-migrate CLI.
user-invocable: true
disable-model-invocation: false
---

# deev — Python Entity Framework SKILL

## 1. Installation

```bash
pip install deev                    # core package (SQLite built-in)
pip install "deev[mongodb]"         # add MongoDB support
pip install "deev[mysql]"           # add MySQL support
pip install "deev[dev]"             # development dependencies/tools
```

Requires **Python >= 3.11**. Dependencies: `appsettings2`, `hanaro`.

## 2. Entity Definition

Entities are defined with the `@entity` decorator (a `dataclass_transform`). It injects an `__init__` that applies field defaults and constructs parameterized keyword arguments.

```python
from datetime import datetime, timezone
from deev import entity, field
from typing import Optional

@entity(table_name='users')                      # bare form — use @entity or @entity(table_name='...')
class User:
    id: int = field(autoincrement=True, primary_key=True)
    name: str
    email: Optional[str]         # auto: nullable=True (detected from type hint)
    age: int = field(min=0, max=150)
    created_at: datetime = field(
        default=lambda: datetime.now(timezone.utc)
    )
```

Key behaviors:

- **Table name**: auto-pluralizes class name via `pluralize()` (simple English rules; if already ends with 's', unchanged). Override with `table_name=`, or disable pluralization entirely with `no_pluralization=True`.
- **Spec caching**: entity spec is stored on `__deev_entity__` at decoration time. Repeated decoration returns the cached spec.
- **Nullable inference**: `Optional[X]` or `Union[..., None]` type hints auto-set `nullable=True`. Override with `nullable=False` on `field()`.
- **Immutable specs**: `EntityFieldSpec` is frozen via `_ImmutableMixin.__freeze__()` after decoration. Do not modify post-decoration.

## 3. Field Options (`field()`)

All parameters are keyword-only:

| Parameter | Type | Effect |
|-----------|------|--------|
| `autoincrement` | `bool \| None` | Mark for auto-increment (INTEGER PK in SQLite) |
| `default` | `Any \| Callable` | Default value; callable invoked at `__init__`. Pass nothing for no default. |
| `index` | `str \| None` | Field is part of an index (names the index) |
| `mapped` | `bool \| None` | Exclude from `splat()`/`hydrate()` operations |
| `max` | `int / float / Decimal` | Validation: max length for str, max value for numeric |
| `min` | `int / float / Decimal` | Validation: min length for str, min value for numeric |
| `nullable` | `bool \| None` | Explicit null override (overrides type-hint inference) |
| `primary_key` | `bool \| None` | Marks field as part of primary key |
| `dbtype` | `str \| None` | Override auto-detected database column type |
| `unique` | `bool \| None` | Adds UNIQUE constraint |
| `validator` | `Callable[[Any], ValidationError \| None]` | Custom validation callback |
| `init` | `bool` | Include in `__init__` parameter list (default: `True`) |

## 4. Connection String Format

ADO-style key-value pairs separated by `;`:

```
Server=host;Database=db_name;Provider=sqlite3;UID=user;PWD=pass;Connection Timeout=3;Command Timeout=9
```

Parseable keys (case-insensitive): `server`, `database`, `uid`/`user`/`user id`/`username`, `pwd`/`password`/`pass`, `provider`, `connection timeout`, `command timeout`.

**Provider dispatch** (used by `connect()` and `create_table_adapter()`):

| Provider value | Python driver | Package required |
|----------------|---------------|-----------------|
| `sqlite` or `sqlite3` | `sqlite3` (stdlib) | none |
| `mysql` or `mysql.connector` | `mysql.connector` | optional `[mysql]` |
| `mongodb` or `pymongo` | `pymongo` | optional `[mongodb]` |

```python
from deev import connect, entity, field
from deev.utils import create_database, create_table_adapter

connection_str = 'Server=./data;Database=mydb;Provider=sqlite3'
create_database(connection_str)

with connect(connection_str) as db:               # DbConnection returned, use as context manager
    adapter = create_table_adapter(User, db)       # factory dispatches to correct provider
    # or directly: from deev.sqlite import SqliteTableAdapter; adapter = SqliteTableAdapter[User](db)
```

`connect()` accepts `ConnectionString | str`. Defaults: `connect_timeout=3`, `command_timeout=9`.

## 5. Table Adapter CRUD

The `DbTableAdapter[TEntity]` Protocol (satisfied by all providers):

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `create_table()` | `() -> None` | — | Creates table from entity spec |
| `create(entity=None, **kwargs)` | `(entity: TEntity \| None, **kwargs) -> dict[str, Any]` | PK values as dict | Returns primary key values |
| `read(**kwargs)` | `(**kwargs) -> TEntity \| None` | Entity or None | By primary key |
| `update(entity)` | `(entity: TEntity) -> None` | — | Updates by primary key |
| `delete(**kwargs)` | `(**kwargs) -> None` | — | Deletes by primary key |
| `exists(**kwargs)` | `(**kwargs) -> bool` | bool | By primary key |
| `upsert(entity)` | `(entity: TEntity) -> dict[str, Any]` | PK values | Insert or update |
| `query(where, params, orderby, limit)` | `(where=None, params=None, orderby=None, limit=None) -> Generator[TEntity, None, None]` | Generator | All kwargs optional |
| `commit()` / `rollback()` | `() -> None` | — | Transaction control |

**SQL parameterization**: all providers use `%?` syntax (normalized across SQLite/MySQL/MongoDB).

```python
from deev import connect
from deev.sqlite import SqliteTableAdapter

with connect(connection_str) as db:
    table = SqliteTableAdapter[User](db)
    pk = table.create(User(name="Alice"))         # → {"id": 1}
    user = table.read(**pk)                        # → User instance
    for u in table.query(where='name LIKE %?', params=('%Alic%',)):
        print(u.name)
```

## 6. Translation (splat / hydrate)

### `splat()` — entity → dict

```python
from deev.translation import splat

# Entity attributes as Python values:
data = splat(user)                     # {"id": 1, "name": "Alice", ...}

# Convert for database storage (applies to_sqlobject()):
sql_data = splat(user, to_sql=True)    # datetime→isoformat, UUID→hex, collections→JSON, ...
```

### `hydrate()` — dict → entity (in-place)

```python
from deev.translation import hydrate

# Python values → entity:
user = hydrate(User(), {"id": 1, "name": "Alice"})

# SQL values → entity (applies to_pyobject()):
hydrated = hydrate(User(), row_from_db, from_sql=True)
```

### `deunionize()` — type hint helper

Extracts the inner type from `Optional[X]` or `Union[X, None]` for use with `to_pyobject()`.

### Custom Serialization

```python
from deev.translation import configure_serialization, DeevJsonEncoder, DeevJsonDecoder

class MyEncoder(DeevJsonEncoder): ...
configure_serialization(encoder=MyEncoder, decoder=MyDecoder)

# Or wholesale replacement:
configure_serialization(serializer=my_serialize, deserializer=my_deserialize)
```

Default `DeevJsonEncoder` supports: datetime (`dt`), date (`date`), time (`time`), Decimal (`r`), UUID (`u`), set (`s`), tuple (`t`), bytes (base64, `b`) — all stored as JSON strings with tick-delimited type codes.

### Type Mapping Reference

| Python type | SQLite | MySQL | MongoDB |
|-------------|--------|-------|---------|
| int | INTEGER | BIGINT | int32 |
| float | REAL | DOUBLE | double |
| Decimal | NUMERIC | DECIMAL(20,10) | decimal |
| str | TEXT | VARCHAR(20)+ | string |
| bool | INTEGER (0/1) | BIT | bool |
| list / dict / tuple / set | TEXT(JSON) | MEDIUMTEXT(JSON) | array / object |
| UUID | TEXT(hex) | CHAR(32) | string |
| datetime | DATETIME(iso) | DATETIME(6)(iso) | datetime |
| date | DATE(iso) | DATE(iso) | date |
| time | TIME(iso) | TIME(6)(iso) | time |
| timedelta | INTEGER(us) | BIGINT | int64 |

## 7. Validation

```python
from deev.validation import validate, ValidationError

errors = validate(user)        # None if valid, list[ValidationError] if not

if errors:
    for e in errors:
        print(f"{e.field_name}: {e.reason}")   # "age": "VAL < 0"

# Custom validator:
def must_be_positive(v):
    if v is not None and v <= 0:
        return ValidationError('price', 'must be positive')
    return None

@entity
class Product:
    id: int = field(autoincrement=True, primary_key=True)
    price: float = field(validator=must_be_positive)
```

Built-in checks: `min`/`max` on string length (LEN) and numeric values (VAL), `nullable=False` enforcement. Custom validators receive the field value, return `ValidationError(reason)` or `None`.

## 8. Migrations

### CLI

```bash
db-migrate apply <migration-name> <connection> [path]
db-migrate undo  <migration-name> <connection> [path]
```

- `<migration-name>`: Target migration to process (use `"all"` for all).
- `<connection>`: Named connection from appsettings2 config or a literal `key=value` connection string.
- `[path]`: Optional migration directory. Defaults to `./migrations/<database_name>/`.

### Migration Scripts

Each file in the migrations directory must define two functions with explicit `commit()` calls:

```python
from deev.common import DbTransactionContext

def apply(db_transaction: DbTransactionContext) -> None:
    db_transaction.execute_nonquery('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)')
    db_transaction.commit()     # MUST be called explicitly

def undo(db_transaction: DbTransactionContext) -> None:
    db_transaction.execute_nonquery('DROP TABLE IF EXISTS users')
    db_transaction.commit()     # MUST be called explicitly
```

**Ordering**: `apply()` processes files in **alphabetical** order; `undo()` processes in **reverse alphabetical** order. Filenames determine order — use numeric prefixes (``001_``, ``002_``, ...) or date codes to guarantee ordering.

**Commit requirement**: The migrator does not auto-commit on behalf of migration scripts. If you forget to call `commit()`, the context manager exit handler raises a ``DbError``.

### Programmatic API

```python
from deev.utils import apply_migrations, undo_migrations

apply_migrations('all', connection_string, './migrations/')     # or '001_create_users' for single migration
undo_migrations('all', connection_string, './migrations/')
```

Migration history is stored in `_migrationdata` (table on SQL providers, collection on MongoDB) with:
- **int auto-increment PK** for MySQL / SQLite
- **UUID PK** for MongoDB (uses ``_MigrationData2`` entity internally)

### Provider-Specific Notes

**MySQL / SQLite — DDL auto-commits**: Both MySQL and SQLite implicitly commit the active transaction before DDL statements (``CREATE``, ``DROP``, ``ALTER``, etc.). This means DML changes issued before DDL in the same migration are committed automatically and **cannot be rolled back together**. If atomicity matters, split DDL and data changes into separate migration scripts.

**MongoDB — no DDL**: MongoDB is schema-less; collections are created implicitly on first insert. The transaction context uses real ``pymongo.ClientSession`` transactions. Nested (savepoint-level) transactions are NOPs — only the top-level ambient transaction matters.

## 9. Error Types

| Exception | Import | When raised |
|-----------|--------|-------------|
| `DbError` | `from deev import DbError` | Unsupported provider, missing DB component in connection string |
| `ValidationError` | `from deev.validation import ValidationError` | Explicit instantiation; returned by `validate()` (as list) |

## 10. Testing Conventions

- Uses **punit** framework (not pytest). Run:
  ```bash
  PYTHONPATH=src coverage run -m punit --trait '!integration' --trait '!hardcoded' --trait '!longrunning' --trait '!manual'
  ```
- Key decorators: `@fact` (single test), `@theory` + `@inlinedata(...)` (parameterized), `@setup`/`@teardown` (lifecycle)
- Entity specs are cached on decoration — use unique class names per test to avoid spec collision.

```python
from deev import entity, field
from punit import fact, theory, inlinedata

@entity
class TestEntity:
    id: int = field(autoincrement=True, primary_key=True)
    name: str

@fact
def test_entity_defaults() -> None:
    e = TestEntity(name="hello")
    assert e.name == "hello"

@theory
@inlinedata("valid", True)
@inlinedata("", False)
def test_name_check(name: str, ok: bool) -> None:
    ...
```

## 11. Code Style for Contributors

- **SPDX headers** on every file (two lines): `# SPDX-FileCopyrightText: © 2023 Shaun Wilson` + `# SPDX-License-Identifier: MIT`
- `from __future__ import annotations` as first import after SPDX/comments
- **Heavy typing**: Protocol, Generic[TEntity], TypeVar, full parameter/return annotations everywhere
- **No docstrings** in `@dataclass_transform` areas; use inline comments (`# NOTE: ...`)
- **Double-underscore** for private attributes (`__field_name`); access via `object.__getattribute__`
- **Immutable specs**: `_ImmutableMixin` with `__freeze__()` — raises `AttributeError` after freezing
- **Protocol-based interfaces** (not ABCs) for all abstractions: DbConnection, DbContext, DbCursor, DbTableAdapter[TEntity], DbTypeMapper, DbTransactionContext
- Graceful optional imports (try/except around mysql/mongodb imports)
- Explicit `__all__` exports on every module
