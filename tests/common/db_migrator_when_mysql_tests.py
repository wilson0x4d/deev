# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import os
import uuid
from typing import Any, Tuple, cast

import appsettings2
from deev._migration_data import _MigrationData, _MigrationData2
from deev.common import ConnectionString
from deev.common.db_migrator import DbMigrator
from punit import fact, sequential, trait


def _get_connection(name: str) -> ConnectionString:
    """Get a named connection string from appsettings.local.json."""
    config = appsettings2.get_configuration()
    raw = getattr(config.connections, name)
    return ConnectionString(raw)


def _scalar(cursor: Any, sql: str) -> int:
    """Execute a scalar SQL query and return the first column value."""
    cursor.execute(sql)
    result = cursor.fetchone()
    assert result is not None
    casted: Tuple[int, ...] = cast(Tuple[int, ...], result)
    return casted[0]


_MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'migrations')


@fact
@trait('integration')
@trait('mysql')
@sequential
def bvt_mysql_applies_all_migrations_and_records_them() -> None:
    """Full apply on live MySQL, 3 rows in _migrationdata, uses _MigrationData (int PK)."""
    cs = _get_connection('mysql_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    cs.database = test_db

    from deev.utils import connect, create_database
    try:
        create_database(cs)

        migrator = DbMigrator(cs)
        migrations_path = os.path.join(_MIGRATIONS_DIR, 'mysql_test')
        migrator.apply(migrations_path, 'all')

        # Verify _migrationdata table has 3 rows
        with connect(cs) as conn:
            cursor = conn.cursor()
            count = _scalar(cursor, 'SELECT COUNT(*) FROM _migrationdata')
            assert count == 3

        # Verify the type selection is _MigrationData (int PK) for MySQL
        migrator2 = DbMigrator(_get_connection('mysql_test'))
        migrator2._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]
        assert migrator2._DbMigrator__migrationdata_t is _MigrationData  # type: ignore[attr-defined]
    finally:
        with connect(cs) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            conn.commit()


@fact
@trait('integration')
@trait('mysql')
@sequential
def bvt_mysql_skips_reapply() -> None:
    """Re-apply produces same row count (idempotency)."""
    cs = _get_connection('mysql_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    cs.database = test_db

    from deev.utils import connect, create_database
    try:
        create_database(cs)

        migrator = DbMigrator(cs)
        migrations_path = os.path.join(_MIGRATIONS_DIR, 'mysql_test')
        migrator.apply(migrations_path, 'all')

        with connect(cs) as conn:
            cursor = conn.cursor()
            count_first = _scalar(cursor, 'SELECT COUNT(*) FROM _migrationdata')

        # Re-apply
        migrator.apply(migrations_path, 'all')

        with connect(cs) as conn:
            cursor = conn.cursor()
            count_second = _scalar(cursor, 'SELECT COUNT(*) FROM _migrationdata')

        assert count_first == count_second
    finally:
        with connect(cs) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            conn.commit()


@fact
@trait('integration')
@trait('mysql')
@sequential
def bvt_mysql_undo_clears_all_records() -> None:
    """undo('all') clears all _migrationdata records."""
    cs = _get_connection('mysql_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    cs.database = test_db

    from deev.utils import connect, create_database, apply_migrations, undo_migrations
    try:
        create_database(cs)

        # Apply all migrations
        apply_migrations('all', cs, os.path.join(_MIGRATIONS_DIR, 'mysql_test'))

        # Verify _migrationdata has 3 rows
        with connect(cs) as conn:
            cursor = conn.cursor()
            assert _scalar(cursor, 'SELECT COUNT(*) FROM _migrationdata') == 3

        # Undo all migrations
        undo_migrations('all', cs, os.path.join(_MIGRATIONS_DIR, 'mysql_test'))

        # Verify _migrationdata is empty
        with connect(cs) as conn:
            cursor = conn.cursor()
            remaining = _scalar(cursor, 'SELECT COUNT(*) FROM _migrationdata')
            assert remaining == 0
    finally:
        with connect(cs) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            conn.commit()


@fact
@trait('integration')
@trait('mysql')
@sequential
def bvt_mysql_users_table_has_seeded_data() -> None:
    """Live query on users table confirms seed data."""
    cs = _get_connection('mysql_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    cs.database = test_db

    from deev.utils import connect, create_database
    try:
        create_database(cs)

        migrator = DbMigrator(cs)
        migrations_path = os.path.join(_MIGRATIONS_DIR, 'mysql_test')
        migrator.apply(migrations_path, 'all')

        with connect(cs) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, email FROM users ORDER BY id')
            rows = cursor.fetchall()
            assert len(rows) == 2, f'expected 2 got {len(rows)}'
            names = {r[0] for r in rows}
            assert 'Alice' in names
            assert 'Bob' in names
    finally:
        with connect(cs) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DROP DATABASE IF EXISTS `{test_db}`')
            conn.commit()
