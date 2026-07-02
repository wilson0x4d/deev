---
name: deev
description: deev Python entity framework — define entities with @entity and field(), perform CRUD via TableAdapter, translate between entity/dict/SQL via splat()/hydrate(), validate entities, manage migrations. Use as a reference document for deev API and concepts.
user-invocable: true
disable-model-invocation: false
type: reference
---

# deev — AI-First Library Reference

**deev** is an entity framework for Python 3.11+. It lets you perform CRUD using Python objects instead of hand-crafting SQL, provides a migration CLI (`db-migrate`), and abstracts across SQLite, MySQL, and MongoDB behind PEP 249-compatible protocols.

---

## Installation

```bash
pip install deev          # core
pip install deev[mongodb] # add MongoDB support
pip install deev[mysql]   # add MySQL support
```

---

## 1. Defining Entities

Decorate a class with `@entity` and annotate its fields. Use `field(...)` from `deev` to configure PK, autoincrement, nullability, validation bounds, etc.

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

### `field(...)` parameters

| Parameter    | Type                            | Meaning                                                         |
|--------------|---------------------------------|-----------------------------------------------------------------|
| `autoincrement` | `bool`                       | Column is auto-increment (PK only). Default: `False`.           |
| `default`      | `Any \| Callable`               | Static value or callable producing a value at instantiation.    |
| `index`        | `str \| IndexOptions`           | Name of an index, or `IndexOptions(...)` descriptor.            |
| `mapped`       | `bool`                           | If `False`, field is excluded from SQL translation.             |
| `min`          | `int \| float \| Decimal`       | Minimum value (strings: min length, numeric: min value).        |
| `max`          | `int \| float \| Decimal`       | Maximum value (strings: max length, numeric: max value).        |
| `nullable`     | `bool`                           | `True` allows NULL. Inferred from `Optional[...]` automatically.|
| `primary_key`  | `bool`                           | Mark the field as part of the PK.                               |
| `dbtype`       | `str`                            | Override the auto-detected DB type.                             |
| `unique`       | `bool`                           | Add a unique constraint.                                        |
| `validator`    | `Callable[[Any], ValidationError \| None]` | Custom validation function. Return `None` to pass.      |

### `@entity` parameters

| Parameter        | Type     | Meaning                                                       |
|------------------|----------|---------------------------------------------------------------|
| `table_name`     | `str`    | Override auto-generated table name (pluralized class name).   |
| `no_pluralization` | `bool` | If `True`, use class name as-is (don't pluralize).            |

### Defining indexes

```python
from deev import entity, field
from deev.entities import IndexOptions, IndexOrder

@entity
class Post:
    id: int = field(autoincrement=True, primary_key=True)
    title: str = field(index='idx_post_title')          # shorthand: by index name
    author: str = field(index=IndexOptions(
        name='idx_post_author', direction=IndexOrder.DESCENDING, rank=1
    ))
```

### Custom table names and non-pluralized names

```python
@entity(table_name='users')
class Users:
    ...

@entity(no_pluralization=True)
class Category:
    ...  # table_name stays "Category", not "Categorys"
```

---

## 2. Connecting to a Database

Use `deev.connect(...)` with a SQL-connection-string style string. It returns a context-managed `DbConnection`.

```python
from deev import connect

conn_str = 'Server=./data/;Database=mydb.db;Provider=sqlite3'
# MySQL:  'Server=localhost;Database=mydb;UID=root;PWD=secret;Provider=mysql'
# MongoDB: 'Server=localhost;Database=mydb;Provider=mongodb'

with connect(conn_str) as db:
    ...
```

Timeouts can be specified in the connection string or as kwargs:

```python
with connect(conn_str, connect_timeout=5, command_timeout=15) as db:
    ...
```

### Supported providers

| Provider string      | Package required    |
|----------------------|---------------------|
| `sqlite3` / `sqlite` | Built-in `sqlite3`  |
| `mysql` / `mysql.connector` | `mysql-connector-python` |
| `mongodb` / `pymongo` | `pymongo`           |

### Creating a database

```python
from deev.utils import create_database

create_database(conn_str)  # creates DB if it doesn't exist
```

---

## 3. Table Adapters (CRUD)

Create a typed table adapter using Python 3.12+ generic syntax:

```python
from deev.sqlite import SqliteTableAdapter

with connect(conn_str) as db:
    table = SqliteTableAdapter[User](db)
    table.create_table()  # DDL
```

The same interface exists for MySQL (`MysqlTableAdapter`) and MongoDB (`MongoTableAdapter`).

### Helper: auto-create table adapter from connection string

```python
from deev.utils import create_table_adapter

table = create_table_adapter(User, conn_str)  # auto-detects provider
```

### `SqliteTableAdapter[User]` methods

| Method     | Signature                                                    | Returns                              |
|------------|--------------------------------------------------------------|--------------------------------------|
| `create`   | `create(entity: User, \| \*\*kwargs) -> dict[str, Any]`     | `{id: <pk_value>}`                   |
| `read`     | `read(\*\*pk_kwargs) -> User \| None`                       | Single entity, or `None`             |
| `update`   | `update(entity: User) -> None`                              | —                                    |
| `delete`   | `delete(\*\*pk_kwargs) -> None`                             | —                                    |
| `exists`   | `exists(\*\*pk_kwargs) -> bool`                             | `True` if found                      |
| `upsert`   | `upsert(entity: User) -> dict[str, Any]`                    | `{id: <pk_value>}`                   |
| `query`    | `query(where?, params?, orderby?, limit?) -> Generator[...]` | Yields `User` objects               |
| `create_table` | `create_table() -> None`                                  | —                                    |

### Examples

```python
# CREATE
pk = table.create(User(name="Alice", email="a@b.com"))
# pk == {"id": 1}

# READ
user = table.read(id=1)

# UPDATE
user.email = "alice@new.com"
table.update(user)

# DELETE
table.delete(id=1)

# EXISTS
table.exists(id=1)  # False

# UPSERT (insert or update on PK match)
pk = table.upsert(User(id=2, name="Bob", email="b@c.com"))

# QUERY
results = table.query(
    where='score > %? AND name LIKE %?',
    params=(50, 'A%'),
    orderby='score DESC',
    limit=10
)
for user in results:
    print(user.name, user.score)
```

### Parameter syntax

All providers use normalized `%?` placeholders, translated automatically at runtime:
- SQLite → `?`
- MySQL → `%s` (native prepared statements)
- MongoDB → passed through

---

## 4. Translation: `splat()` / `hydrate()`

Convert between entity objects and dictionaries.

```python
from deev.translation import splat, hydrate

# Entity → dict (useful for partial updates, logging, etc.)
user = User(name="Alice", score=42)
d = splat(user)
# {"id": 1, "name": "Alice", "email": None, "score": 42, "created": datetime(...)}

d_sql = splat(user, to_sql=True)  # serialize complex types for DB storage

# Dict → entity (from DB query results)
row = {"id": 3, "name": "Charlie", "score": 77, "created": "2025-01-01T00:00:00+00:00"}
user = hydrate(User, row, from_sql=True)
# User(id=3, name="Charlie", score=77, created=datetime(...))

# Hydrate into existing entity
hydrate(user, row)  # modifies in-place
```

### Supported complex types (auto-serialized to JSON)

`list`, `dict`, `set`, `tuple`, `Decimal`, `UUID`, `datetime`, `date`, `time`, `timedelta`, `bytes`

### Custom serialization

```python
from deev.translation import configure_serialization
import json

configure_serialization(
    encoder=MyCustomEncoder,
    decoder=MyCustomDecoder
)
# or replace entirely:
configure_serialization(
    serializer=my_serialize_fn,
    deserializer=my_deserialize_fn
)
```

---

## 5. Validation

Entities validate before persistence automatically. You can also validate on demand.

```python
from deev.validation import validate, ValidationError

user = User(name="", score=200)  # violates max=100
errors = validate(user)
# [ValidationError("score"): "VAL > 100"]
```

Custom validators per field:

```python
@entity
class Account:
    pin: int = field(validator=lambda v: None if str(v).isdigit() and len(str(v)) == 4 else ValidationError("pin", "must be 4 digits"))
```

---

## 6. Transaction Contexts

Enter a transactional scope using `begin_transaction()` or provider-specific contexts.

```python
from deev.utils import begin_transaction

with begin_transaction(conn_str) as tx:
    table = create_table_adapter(User, tx)
    table.create(User(name="Alice"))
    table.create(User(name="Bob"))
    tx.commit()  # required — migration writer must call this explicitly
```

### `DbTransactionContext` methods

| Method           | Signature                                    | Returns            |
|------------------|----------------------------------------------|--------------------|
| `cursor`         | `cursor() -> DbCursor`                      | —                  |
| `commit`         | `commit() -> None`                          | —                  |
| `rollback`       | `rollback() -> None`                        | —                  |
| `execute`        | `execute(sql, params?) -> DbCursor`          | Cursor             |
| `execute_script` | `execute_script(sql) -> None`                | —                  |
| `execute_nonquery`| `execute_nonquery(sql, params?) -> None`    | —                  |
| `execute_reader` | `execute_reader(sql, params?) -> Generator[...]` | Yields tuples  |
| `execute_scalar` | `execute_scalar(sql, params?) -> Any`        | Single value       |

### Raw SQL example

```python
with begin_transaction(conn_str) as tx:
    count = tx.execute_scalar('SELECT COUNT(*) FROM Users WHERE score > %?', (50,))
    tx.rollback()  # or tx.commit()
```

---

## 7. Database Migrations with `db-migrate` CLI

### Basic usage

```bash
# Apply migrations
db-migrate apply 'Server=./data/;Database=mydb;Provider=sqlite3' ./migrations/mydb/

# Undo last migration
db-migrate undo --stop-at "002_somemigration" 'Server=...' ./migrations/mydb/

# Undo all
db-migrate undo 'Server=...' ./migrations/mydb/

# Use a named connection from appsettings2 config
db-migrate apply my_production
```

### Creating a migration script

```python
# migrations/mydb/001_create_users.py
from deev.common import DbTransactionContext
from deev.utils import create_table_adapter
from myapp.entities import User

def apply(tx: DbTransactionContext) -> None:
    table = create_table_adapter(User, tx)
    table.create_table()
    tx.commit()  # REQUIRED: must call explicitly

def undo(tx: DbTransactionContext) -> None:
    tx.execute_nonquery('DROP TABLE IF EXISTS Users')
    tx.commit()
```

### Migration conventions

- **Ordering**: alphabetical by filename. Prefix with numbers: `001_`, `002_`, ...
- **Tracking**: applied migrations stored in `_migrationdata` table/collection.
- **Idempotency**: the CLI skips already-applied migrations.
- **Stop-at point**: `--stop-at "migration_name"` halts processing at that file.

---

## 8. ConnectionString

Parse and build connection strings programmatically.

```python
from deev import ConnectionString

cs = ConnectionString('Server=localhost;Database=prod;UID=admin;PWD=s3cret;Provider=mysql')
print(cs.server)      # "localhost"
print(cs.database)    # "prod"
print(cs.user)        # "admin"
print(cs.provider)    # "mysql"

str(cs)  # "Server=localhost;Database=prod;UID=admin;PWD=s3cret;Provider=mysql"
```

Supported keys: `Server`, `Database`, `UID`/`User`/`Username`, `PWD`/`Password`/`Pass`, `Provider`, `Connection Timeout`, `Command Timeout`.

---

## 9. Error Handling

```python
from deev import DbError

try:
    table.create(...)
except DbError as e:
    print(e.reason)  # descriptive error message
```

---

## 10. Provider Type Mappings

| Python type      | SQLite      | MySQL              |
|------------------|-------------|--------------------|
| `int`            | `INTEGER`   | `INT`              |
| `float`          | `REAL`      | `DOUBLE`           |
| `str`            | `TEXT`      | `TEXT`             |
| `bool`           | `INTEGER`   | `TINYINT`          |
| `datetime`       | `TEXT` (ISO) | `DATETIME`        |
| `date`           | `TEXT` (ISO) | `DATE`            |
| `bytes`          | `BLOB`      | `BLOB`             |
| `list` / `dict`  | `TEXT` (JSON) | `TEXT` (JSON)   |

Override with `dbtype="..."` on any field.

---

## 11. MongoDB-specific notes

- Collections are created implicitly on first insert — no DDL needed.
- The `_migrationdata` uses UUID PKs (MongoDB doesn't support auto-increment).
- Native `apply(...)` and `undo(...)` signatures are the same, but DDL auto-commit doesn't apply.
- Access `mongo_client`, `mongo_database`, `mongo_session` properties on the transaction object for advanced operations.

```python
def apply(tx: DbTransactionContext) -> None:
    # tx.mongo_session is a pymongo.ClientSession
    # tx.mongo_database is a pymongo.Database
    ...
```

---

## Quick Reference: Entry Points

| Import from `deev`                  | What it provides                        |
|--------------------------------------|----------------------------------------|
| `entity`                             | Decorator to define entity classes     |
| `field`                              | Configure entity fields                |
| `connect`                            | Create a context-managed DB connection |
| `ConnectionString`                   | Parse/build connection strings           |
| `DbError`                            | DB operation error exception             |
| `common.DbTransactionContext`        | Protocol for transactional scope         |
| `validation.validate`                | On-demand entity validation              |
| `translation.splat` / `hydrate`      | Entity ↔ dict conversion                 |
| `utils.create_database`              | Create DB if missing                     |
| `utils.create_table_adapter`         | Auto-detect provider, return adapter     |
| `utils.begin_transaction`            | Start a transactional scope              |

Provider adapters:
- `deev.sqlite.SqliteTableAdapter[Entity](db)`
- `deev.mysql.MysqlTableAdapter[Entity](db)`
- `deev.mongodb.MongoTableAdapter[Entity](db)`
