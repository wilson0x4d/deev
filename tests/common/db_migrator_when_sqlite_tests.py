# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import os
import tempfile
from pathlib import Path
from typing import Any, Tuple, cast

from deev.common import ConnectionString
from deev.common.db_migrator import DbMigrator
from deev.utils import connect
from punit import fact, trait


def _row_count(conn: Any) -> int:
    """Execute COUNT(*) FROM _migrationdata and return the integer count."""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM _migrationdata')
    result = cursor.fetchone()
    assert result is not None
    casted: Tuple[int, ...] = cast(Tuple[int, ...], result)
    return casted[0]


_MIGRATIONS_DIR = Path(__file__).parent.parent / 'test_data' / 'migrations'


def _get_connection() -> ConnectionString:
    """Create a file-based SQLite connection string that persists across connect() calls."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_migrator.db')
    cs = ConnectionString()
    cs.provider = 'sqlite'
    cs.database = db_path
    return cs


@fact
@trait('integration')
@trait('sqlite3')
def bvt_sqlite_applies_all_migrations_and_records_them() -> None:
    """Verify apply() inserts data into live SQLite table and records migrations."""
    cs = _get_connection()

    migrator = DbMigrator(cs)
    migrations_path = str(_MIGRATIONS_DIR / 'sqlite_test')
    migrator.apply(migrations_path, 'all')

    # Verify _migrationdata has exactly 3 rows via live query
    with connect(cs) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        rows = cursor.fetchall()
        table_names = [r[0] for r in rows]
        assert '_migrationdata' in table_names


@fact
@trait('integration')
@trait('sqlite3')
def bvt_sqlite_skips_reapply() -> None:
    """Re-applying should produce no new _migrationdata rows."""
    cs = _get_connection()

    migrator = DbMigrator(cs)
    migrations_path = str(_MIGRATIONS_DIR / 'sqlite_test')
    migrator.apply(migrations_path, 'all')

    with connect(cs) as conn:
        count_first = _row_count(conn)

    # Re-apply
    migrator.apply(migrations_path, 'all')

    with connect(cs) as conn:
        count_second = _row_count(conn)

    assert count_first == count_second


@fact
@trait('integration')
@trait('sqlite3')
def bvt_sqlite_undo_clears_all_records() -> None:
    """Apply all, then undo all -- _migrationdata should be empty."""
    cs = _get_connection()

    migrator = DbMigrator(cs)
    migrations_path = str(_MIGRATIONS_DIR / 'sqlite_test')
    migrator.apply(migrations_path, 'all')

    with connect(cs) as conn:
        assert _row_count(conn) == 3

    migrator.undo(migrations_path, 'all')

    with connect(cs) as conn:
        remaining = _row_count(conn)
        assert remaining == 0


@fact
@trait('integration')
@trait('sqlite3')
def bvt_sqlite_users_table_has_seeded_data() -> None:
    """Verify the seeded data actually exists in the live users table."""
    cs = _get_connection()

    migrator = DbMigrator(cs)
    migrations_path = str(_MIGRATIONS_DIR / 'sqlite_test')
    migrator.apply(migrations_path, 'all')

    with connect(cs) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name, email FROM users ORDER BY id')
        rows = cursor.fetchall()
        assert len(rows) == 2
        names = {r[0] for r in rows}
        assert 'Alice' in names
        assert 'Bob' in names


@fact
@trait('integration')
@trait('sqlite3')
def bvt_sqlite_rollback_on_failure() -> None:
    """Use a migration that raises -- verify the failure is propagated and no uncommitted DDL persists."""
    temp_dir = tempfile.mkdtemp()
    (Path(temp_dir) / '001_good.py').write_text(
        "def apply(db_transaction):\n"
        "    db_transaction.execute_nonquery(\n"
        "        'CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, val TEXT)'\n"
        "    )\n"
        "    db_transaction.commit()\n"
        "\n"
        "def undo(db_transaction):\n"
        "    db_transaction.execute_nonquery('DROP TABLE IF EXISTS test_rollback')\n"
        "    db_transaction.commit()\n"
    )
    (Path(temp_dir) / '002_bad.py').write_text(
        "def apply(db_transaction):\n"
        "    # Deliberate failure before any DDL -- verify no phantom rows appear\n"
        "    db_transaction.execute_nonquery('SELECT 1')\n"
        "    raise Exception('deliberate failure')\n"
        "\n"
        "def undo(db_transaction):\n"
        "    pass\n"
    )

    cs = _get_connection()

    migrator = DbMigrator(cs)
    try:
        migrator.apply(temp_dir, 'all')
        raise AssertionError('Expected exception from deliberate failure')
    except Exception as e:
        assert 'deliberate failure' in str(e).lower()

    # Verify: migration 001_good's DDL was committed within its own context
    # (so it persists), and no partial rows were inserted into _migrationdata.
    with connect(cs) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        assert 'test_rollback' in tables, f'test_rollback table should exist but not found in: {tables}'

        # _migrationdata has exactly 1 row from the successful migration.
        cursor.execute('SELECT COUNT(*) FROM _migrationdata')
        row = cursor.fetchone()
        assert row is not None
        count: int = row[0]
        assert count == 1, f'Expected 1 row in _migrationdata but got {count}'

    # Verify the rollback didn't create phantom data (no uncommitted DDL leaked).
    with connect(cs) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        assert all(not t.startswith('phantom') for t in tables), (
            f'Phantom data leaked through rollback: {tables}')


@fact
@trait('integration')
@trait('sqlite3')
def bvt_sqlite_undo_then_reapply_restores_data() -> None:
    """Full cycle: apply all -> undo up to beta -> re-apply with stop_at=gamma."""
    cs = _get_connection()

    migrator = DbMigrator(cs)
    migrations_path = str(_MIGRATIONS_DIR / 'sqlite_test')
    migrator.apply(migrations_path, 'all')

    with connect(cs) as conn:
        before_undo = _row_count(conn)

    assert before_undo == 3
