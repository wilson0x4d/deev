# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.mongodb import MongoProxyConnection
import os

import appsettings2
from deev._MigrationData import _MigrationData, _MigrationData2
from deev.common import ConnectionString
from deev.common.DbMigrator import DbMigrator
from deev.utils import connect
from punit import fact, trait, setup
from typing import cast


def _get_connection(name: str) -> ConnectionString:
    """Get a named connection string from appsettings.local.json."""
    config = appsettings2.get_configuration()
    raw = getattr(config.connections, name)
    return ConnectionString(raw)


_MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'migrations')


@setup
def delete_all_collections() -> None:
    """connect to mongodb database and delete all collections"""
    with connect(_get_connection('mongo_test')) as connection:
        db = cast(MongoProxyConnection, connection).mongo_database
        for collection_name in db.list_collection_names():
            db.drop_collection(collection_name)


@fact
@trait('integration')
@trait('mongodb')
def bvt_mongo_applies_all_migrations_and_records_them() -> None:
    """Full apply on live MongoDB, 3 records in _migrationdata, uses _MigrationData2 (UUID PK)."""
    cs = _get_connection('mongo_test')

    migrator = DbMigrator(cs)
    migrations_path = os.path.join(_MIGRATIONS_DIR, 'mongo_test')
    migrator.apply(migrations_path, 'all')

    # Verify _migrationdata collection has 3 documents
    migrator2 = DbMigrator(cs)
    migrations_table = migrator2._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]  # noqa: SLF001
    all_rows = list(migrations_table.query())
    assert len(all_rows) == 3

    # Verify the type selection is _MigrationData2 (UUID PK) for MongoDB
    assert migrator2._DbMigrator__migrationdata_t is _MigrationData2  # type: ignore[attr-defined]


@fact
@trait('integration')
@trait('mongodb')
def bvt_mongo_skips_reapply() -> None:
    """Re-apply produces same record count (idempotency)."""
    cs = _get_connection('mongo_test')

    migrator = DbMigrator(cs)
    migrations_path = os.path.join(_MIGRATIONS_DIR, 'mongo_test')
    migrator.apply(migrations_path, 'all')

    migrator2 = DbMigrator(cs)
    migrations_table = migrator2._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]  # noqa: SLF001
    count_first = len(list(migrations_table.query()))

    # Re-apply
    migrator.apply(migrations_path, 'all')

    migrator3 = DbMigrator(cs)
    migrations_table2 = migrator3._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]  # noqa: SLF001
    count_second = len(list(migrations_table2.query()))

    assert count_first == count_second


@fact
@trait('integration')
@trait('mongodb')
def bvt_mongo_undo_clears_all_records() -> None:
    """undo('all') clears all _migrationdata records."""
    cs = _get_connection('mongo_test')

    migrator = DbMigrator(cs)
    migrations_path = os.path.join(_MIGRATIONS_DIR, 'mongo_test')
    migrator.apply(migrations_path, 'all')

    migrator2 = DbMigrator(cs)
    migrations_table = migrator2._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]  # noqa: SLF001
    assert len(list(migrations_table.query())) == 3

    migrator.undo(migrations_path, 'all')

    migrator3 = DbMigrator(cs)
    migrations_table2 = migrator3._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]  # noqa: SLF001
    remaining = len(list(migrations_table2.query()))
    assert remaining == 0


@fact
@trait('integration')
@trait('mongodb')
def bvt_mongo_users_collection_has_documents() -> None:
    """Direct pymongo query on users collection confirms seed data."""
    cs = _get_connection('mongo_test')

    migrator = DbMigrator(cs)
    migrations_path = os.path.join(_MIGRATIONS_DIR, 'mongo_test')
    migrator.apply(migrations_path, 'all')

    # Verify documents exist in the users collection via raw pymongo access
    from deev.utils import connect
    with connect(cs) as conn:
        users_col = getattr(conn, 'mongo_database', None)
        if users_col is not None:
            docs = list(users_col['users'].find())
            assert len(docs) == 2
