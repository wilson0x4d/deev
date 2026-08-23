# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import os
import uuid
from typing import Any, cast

import appsettings2
from deev.common.db_migrator import DbMigrator
from punit import fact, trait, sequential


def _get_connection(name: str) -> str:
    """Get a named connection string from appsettings.local.json."""
    config = appsettings2.get_configuration()
    return cast(str, getattr(config.connections, name))


_MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'migrations')


@fact
@trait('clickhouse')
@trait('integration')
@sequential
def bvt_clickhouse_applies_all_migrations_and_records_them() -> None:
    """Full apply on live ClickHouse, 3 rows in _migrationdata."""
    cs = _get_connection('clickhouse_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    from deev.common.connection_string import ConnectionString
    original_cs = ConnectionString(cs)
    original_cs.database = test_db

    from deev.utils import connect, create_database
    try:
        create_database(original_cs)

        migrator = DbMigrator(original_cs)
        migrations_path = os.path.join(_MIGRATIONS_DIR, 'clickhouse_test')
        migrator.apply(migrations_path, 'all')

        # Verify _migrationdata collection has 3 rows
        with connect(original_cs) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM _migrationdata')
            result = cursor.fetchone()
            assert result is not None
            count = int(result[0])
            assert count == 3

    finally:
        # Clean up: drop the test database
        try:
            with connect(original_cs) as conn:
                conn.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
@sequential
def bvt_clickhouse_re_applies_idempotently() -> None:
    """Re-apply on already applied ClickHouse migrations should be no-op (idempotency)."""
    cs = _get_connection('clickhouse_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    from deev.common.connection_string import ConnectionString
    original_cs = ConnectionString(cs)
    original_cs.database = test_db

    from deev.utils import connect, create_database
    try:
        create_database(original_cs)

        migrator = DbMigrator(original_cs)
        migrations_path = os.path.join(_MIGRATIONS_DIR, 'clickhouse_test')
        migrator.apply(migrations_path, '003_seed_data')

        # Re-apply to same point
        migrator2 = DbMigrator(original_cs)
        migrator2.apply(migrations_path, '003_seed_data')

        # Should still have 3 migration records, not 6
        with connect(original_cs) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM _migrationdata')
            result = cursor.fetchone()
            assert result is not None
            count = int(result[0])
            assert count == 3

    finally:
        try:
            with connect(original_cs) as conn:
                conn.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
@sequential
def bvt_clickhouse_undoes_all_migrations() -> None:
    """Full undo on ClickHouse, _migrationdata should be empty."""
    cs = _get_connection('clickhouse_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    from deev.common.connection_string import ConnectionString
    original_cs = ConnectionString(cs)
    original_cs.database = test_db

    from deev.utils import connect, create_database, apply_migrations
    try:
        create_database(original_cs)

        # Apply all
        apply_migrations('all', original_cs, os.path.join(_MIGRATIONS_DIR, 'clickhouse_test'))

        # Undo all
        from deev.utils import undo_migrations
        undo_migrations('all', original_cs, os.path.join(_MIGRATIONS_DIR, 'clickhouse_test'))

        # Verify _migrationdata is empty
        with connect(original_cs) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM _migrationdata')
            result = cursor.fetchone()
            assert result is not None
            count = int(result[0])
            assert count == 0

    finally:
        try:
            with connect(original_cs) as conn:
                conn.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass


@fact
@trait('clickhouse')
@trait('integration')
@sequential
def bvt_clickhouse_verify_users_table_structure() -> None:
    """Verify the users table has the expected structure after migrations."""
    cs = _get_connection('clickhouse_test')
    test_db = f'deev_migrator_bvt_{uuid.uuid4().hex[:16]}'
    from deev.common.connection_string import ConnectionString
    original_cs = ConnectionString(cs)
    original_cs.database = test_db

    from deev.utils import connect, create_database
    try:
        create_database(original_cs)

        migrator = DbMigrator(original_cs)
        migrations_path = os.path.join(_MIGRATIONS_DIR, 'clickhouse_test')
        migrator.apply(migrations_path, 'all')

        # Verify users table exists and has correct columns
        with connect(original_cs) as conn:
            cursor = conn.cursor()
            cursor.execute('DESCRIBE TABLE users')
            rows = cursor.fetchall()
            cols_set = {row[0] for row in rows}
            assert 'id' in cols_set
            assert 'name' in cols_set
            assert 'email' in cols_set

        # Verify seeded data
        with connect(original_cs) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            result = cursor.fetchone()
            assert result is not None
            assert int(result[0]) == 2

    finally:
        try:
            with connect(original_cs) as conn:
                conn.cursor().execute(f'DROP DATABASE IF EXISTS `{test_db}`')
        except Exception:
            pass
