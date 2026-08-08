# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import os

import appsettings2
from deev._migration_data import _MigrationData, _MigrationData2
from deev.common import ConnectionString, DbError
from deev.common.db_migrator import DbMigrator
from deev.utils import apply_migrations, undo_migrations
from punit.mocks import Mock, patch
from punit import fact, trait
from types import ModuleType
from typing import Any


# Helper to create test rows with real values (punit Mock attributes don't return configured values via .returns())
def _make_row(migration: str, row_id: int):
    """Return a simple object with real string/int attributes for dict/set/comparison use."""
    return type('_Row', (), {'migration': migration, 'id': row_id})()


def _fixture_path(name: str) -> str:
    """Return the path to a migrations fixture directory."""
    return os.path.join(os.path.dirname(__file__), 'migrations', name)


def _get_test_connectionstring(name: str) -> ConnectionString:
    """Get a test connection string from appsettings."""
    configuration = appsettings2.get_configuration()
    connection_str = getattr(configuration.connections, name)
    return ConnectionString(connection_str)


def _apply_mocked(cs: ConnectionString, mock_conn: Mock, mock_adapter: Mock, path: str, *args, **kwargs):  # type: ignore[type-arg]
    """Create a DbMigrator and call apply() with patches in place.

    Uses the provided mock_conn/mock_adapter from the test (NOT _migrator_mocked).
    Configures patches manually — do NOT use 'with' alongside manual __enter__/__exit__.
    """
    conn_patch = patch('deev.utils.connect')
    adapter_patch = patch('deev.utils.create_table_adapter')
    db_patch = patch('deev.utils.create_database')
    tx_patch = patch('deev.utils.begin_transaction')

    cp = conn_patch.__enter__()
    ap = adapter_patch.__enter__()
    db_patch.__enter__()
    tx_patch.__enter__()

    # Configure what connect/create_table_adapter return
    cp().returns(mock_conn)  # type: ignore[attr-defined]
    ap().returns(mock_adapter)  # type: ignore[attr-defined]

    migrator = DbMigrator(cs)
    migrator._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]
    result = migrator.apply(path, *args, **kwargs)  # type: ignore[func-returns-value]

    conn_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    adapter_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    db_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    tx_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    return result


def _undo_mocked(cs: ConnectionString, mock_conn: Mock, mock_adapter: Mock, path: str, *args, **kwargs):  # type: ignore[type-arg]
    """Create a DbMigrator and call undo() with patches in place."""
    conn_patch = patch('deev.utils.connect')
    adapter_patch = patch('deev.utils.create_table_adapter')
    db_patch = patch('deev.utils.create_database')
    tx_patch = patch('deev.utils.begin_transaction')

    cp = conn_patch.__enter__()
    ap = adapter_patch.__enter__()
    db_patch.__enter__()
    tx_patch.__enter__()

    cp().returns(mock_conn)  # type: ignore[attr-defined]
    ap().returns(mock_adapter)  # type: ignore[attr-defined]

    migrator = DbMigrator(cs)
    migrator._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]
    result = migrator.undo(path, *args, **kwargs)  # type: ignore[func-returns-value]

    conn_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    adapter_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    db_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    tx_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    return result


def _migrator_mocked(cs: ConnectionString):  # type: ignore[type-arg]
    """Create a DbMigrator with patched DB dependencies and return (migrator, mock_adapter)."""
    mock_conn = Mock()
    mock_adapter = Mock()
    mock_adapter.create_table.returns(None)
    mock_adapter.commit.returns(None)
    mock_adapter.query.returns(iter([]))
    mock_adapter.create.side_effect = lambda eff: {'id': getattr(eff, 'id', 0)}  # type: ignore[arg-type]
    mock_adapter.delete.returns(None)
    mock_adapter.exists.returns(False)

    conn_patch = patch('deev.utils.connect')
    adapter_patch = patch('deev.utils.create_table_adapter')
    db_patch = patch('deev.utils.create_database')
    tx_patch = patch('deev.utils.begin_transaction')
    resolve_mongodb_auth_source_patch = patch('deev.utils.resolve_mongodb_auth_source')

    cp = conn_patch.__enter__()
    ap = adapter_patch.__enter__()
    db_patch.__enter__()
    tx_patch.__enter__()
    resolve_mongodb_auth_source_patch.__enter__().returns('mongo_test')
    cp().returns(mock_conn)  # type: ignore[attr-defined]
    ap().returns(mock_adapter)  # type: ignore[attr-defined]

    migrator = DbMigrator(cs)
    migrator._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]
    return migrator, mock_adapter, (conn_patch, adapter_patch, db_patch, tx_patch, resolve_mongodb_auth_source_patch)


def _release_patches(patches: tuple):  # type: ignore[type-arg]
    """Release a tuple of patch objects."""
    for p in patches:
        p.__exit__(None, None, None)  # type: ignore[arg-type]


def when_constructed_with_sqlite_provider__then_migration_data_type_is_v1():
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    assert migrator._DbMigrator__migrationdata_t is _MigrationData  # type: ignore[attr-defined]
    _release_patches(patches)


@fact
@trait('unit')
def when_constructed_with_mysql_provider__then_migration_data_type_is_v1() -> None:
    cs = ConnectionString()
    cs.server = 'localhost:3306'
    cs.database = 'testdb'
    cs.provider = 'mysql.connector'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    assert migrator._DbMigrator__migrationdata_t is _MigrationData  # type: ignore[attr-defined]
    _release_patches(patches)


@fact
@trait('unit')
def when_constructed_with_mongodb_provider__then_migration_data_type_is_v2() -> None:
    cs = _get_test_connectionstring('mongo_test')

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    assert migrator._DbMigrator__migrationdata_t is _MigrationData2, f'expected _MigrationData2, got {type(migrator._DbMigrator__migrationdata_t)}'  # type: ignore[attr-defined]
    _release_patches(patches)


@fact
@trait('unit')
def when_constructed_with_pymongo_provider__then_migration_data_type_is_v2() -> None:
    cs = _get_test_connectionstring('mongo_test')

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    assert migrator._DbMigrator__migrationdata_t is _MigrationData2, f'expected _MigrationData2, got {type(migrator._DbMigrator__migrationdata_t)}'  # type: ignore[attr-defined]
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_given_nonexistent_path__then_returns_early_and_logs_warning() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    with patch('logging.Logger.warning'), patch('logging.Logger.info') as ctx_info:  # type: ignore[var-annotated]
        ctx_info.returns(None)
        _apply_mocked(cs, Mock(), mock_adapter, '/nonexistent/path/xyz')
        # .called is the boolean property on punit.Mock (not .was_called which returns a child Mock)
        assert not ctx_info.called or any('applied' in str(c.args[0]) for c in ctx_info.calls)
        assert mock_adapter.create.call_count == 0

    _release_patches(patches)


@fact
@trait('unit')
def when_apply_given_empty_directory__then_returns_early_and_logs_warning() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('empty'))
    assert mock_adapter.create.call_count == 0
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_with_invalid_stop_at__then_logs_error_and_returns_early() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    with patch('logging.Logger.error') as ctx_err, \
            patch('logging.Logger.info'):
        ctx_err.returns(None)
        _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta'), stop_at='nonexistent')

        assert ctx_err.called
        err_msg = str(ctx_err.calls[0].args[0])
        assert 'alpha' in err_msg
        assert 'beta' in err_msg
        assert mock_adapter.create.call_count == 0

    _release_patches(patches)


@fact
@trait('unit')
def when_apply_with_stop_at_all__then_applies_all_migrations() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta_gamma'), stop_at='all')
    assert mock_adapter.create.call_count == 3
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_with_stop_at_star__then_applies_all_migrations() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta'), stop_at='*')
    assert mock_adapter.create.call_count == 2
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_with_specific_stop_at__then_applies_until_that_migration() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta_gamma'), stop_at='beta')
    assert mock_adapter.create.call_count == 2
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_processes_files_sorted_alphabetically() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta_gamma'))
    assert mock_adapter.create.call_count == 3
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_skips_already_applied_migration__then_does_not_reapply() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    # Pre-populate query with alpha already applied (use real values via _make_row)
    r = _make_row('alpha', 1)
    mock_adapter.query.returns(iter([r]))

    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta'))
    assert mock_adapter.create.call_count == 1
    _release_patches(patches)


@fact
@trait('unit')
def when_apply_migration_missing_apply_function__then_raises_DbError() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    try:
        _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('bad_no_apply'))
    except DbError as e:
        assert 'missing `apply`' in str(e).lower() or "missing `apply" in str(e), f'Expected apply error, got: {e}'
    else:
        raise AssertionError('Expected DbError to be raised.')

    _release_patches(patches)


@fact
@trait('unit')
def when_apply_successfully_applies_migration__then_records_in_table_and_calls_commit() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    # Record which entities were created
    created_entities: list[Any] = []

    def capture(eff: Any) -> Mock | None:  # type: ignore[type-arg]
        created_entities.append(eff)
        return None

    mock_adapter.create.side_effect = capture  # type: ignore[arg-type]

    _apply_mocked(cs, Mock(), mock_adapter, _fixture_path('first_only'))

    assert len(created_entities) == 1
    assert created_entities[0].migration == 'first'
    assert mock_adapter.commit.called

    _release_patches(patches)


@fact
@trait('unit')
def when_undo_given_nonexistent_path__then_returns_early_and_logs_warning() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    with patch('logging.Logger.warning'):
        _undo_mocked(cs, Mock(), mock_adapter, '/nonexistent/path/xyz')
        assert mock_adapter.delete.call_count == 0

    _release_patches(patches)


@fact
@trait('unit')
def when_undo_given_empty_directory__then_returns_early_and_logs_warning() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    _undo_mocked(cs, Mock(), mock_adapter, _fixture_path('empty'))
    assert mock_adapter.delete.call_count == 0
    _release_patches(patches)


@fact
@trait('unit')
def when_undo_with_invalid_stop_at_not_in_applied__then_logs_error_and_returns_early() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    # Pre-populate with only 'alpha' applied (use real values via _make_row)
    r = _make_row('alpha', 1)
    mock_adapter.query.returns(iter([r]))

    with patch('logging.Logger.error') as ctx_err, \
            patch('logging.Logger.info'):
        ctx_err.returns(None)
        _undo_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta'), stop_at='nonexistent')

        assert ctx_err.called
        err_msg = str(ctx_err.calls[0].args[0])
        assert 'alpha' in err_msg

    _release_patches(patches)


@fact
@trait('unit')
def when_undo_with_stop_at_all__then_undoes_all_applied_migrations() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    # Pre-populate all three as applied (use real values via _make_row)
    r1, r2, r3 = _make_row('gamma', 3), _make_row('beta', 2), _make_row('alpha', 1)
    mock_adapter.query.returns(iter([r1, r2, r3]))

    _undo_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta_gamma'), stop_at='all')
    assert mock_adapter.delete.call_count == 3
    _release_patches(patches)


@fact
@trait('unit')
def when_undo_with_specific_stop_at__then_undoes_up_to_and_including_that_migration() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    # All three applied, stop at 'beta' (use real values via _make_row)
    r1, r2, r3 = _make_row('gamma', 3), _make_row('beta', 2), _make_row('alpha', 1)
    mock_adapter.query.returns(iter([r1, r2, r3]))

    _undo_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta_gamma'), stop_at='beta')
    assert mock_adapter.delete.call_count == 2
    _release_patches(patches)


@fact
@trait('unit')
def when_undo_processes_migrations_in_reverse_order() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    # All three applied, no stop_at (process all) (use real values via _make_row)
    r1, r2, r3 = _make_row('gamma', 3), _make_row('beta', 2), _make_row('alpha', 1)
    mock_adapter.query.returns(iter([r1, r2, r3]))

    _undo_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta_gamma'))
    assert mock_adapter.delete.call_count == 3
    _release_patches(patches)


@fact
@trait('unit')
def when_undo_skips_already_undone_migration__then_does_not_delete_again() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator, mock_adapter, patches = _migrator_mocked(cs)

    # Only 'beta' is applied (alpha already undone) (use real values via _make_row)
    r = _make_row('beta', 2)
    mock_adapter.query.returns(iter([r]))

    _undo_mocked(cs, Mock(), mock_adapter, _fixture_path('alpha_beta'))
    assert mock_adapter.delete.call_count == 1
    _release_patches(patches)


@fact
@trait('unit')
def when_undo_migration_missing_undo_function__then_raises_DbError() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    mock_adapter = Mock()
    r = _make_row('bad', 1)
    mock_adapter.query.returns(iter([r]))
    mock_adapter.create_table.returns(None)
    mock_adapter.commit.returns(None)

    conn_patch = patch('deev.utils.connect')
    adapter_patch = patch('deev.utils.create_table_adapter')
    db_patch = patch('deev.utils.create_database')
    tx_patch = patch('deev.utils.begin_transaction')

    cp = conn_patch.__enter__()
    ap = adapter_patch.__enter__()
    db_patch.__enter__()
    tx_patch.__enter__()
    cp().returns(Mock())  # type: ignore[attr-defined]
    ap().returns(mock_adapter)  # type: ignore[attr-defined]

    migrator = DbMigrator(cs)
    migrator._DbMigrator__get_or_create_migrations_table()  # type: ignore[attr-defined]

    try:
        migrator.undo(_fixture_path('bad_no_undo'))
    except DbError as e:
        assert 'missing `undo`' in str(e).lower() or "missing `undo" in str(e), f'Expected undo error, got: {e}'
    else:
        raise AssertionError('Expected DbError to be raised.')

    conn_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    adapter_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    db_patch.__exit__(None, None, None)  # type: ignore[arg-type]
    tx_patch.__exit__(None, None, None)  # type: ignore[arg-type]


@fact
@trait('unit')
def when_load_migration_with_valid_path__then_returns_module_with_apply_and_undo() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    filepath = os.path.join(_fixture_path('single_migration'), 'test_migration.py')
    module = DbMigrator(cs)._DbMigrator__load_migration(filepath)  # type: ignore[attr-defined]

    assert isinstance(module, ModuleType), f'Expected ModuleType, got {type(module)}'
    assert hasattr(module, 'apply') and callable(module.apply)
    assert hasattr(module, 'undo') and callable(module.undo)


@fact
@trait('unit')
def when_load_migration_with_invalid_path__raises_no_exception() -> None:
    """The ImportError path in __load_migration is unreachable — spec_from_file_location
    returns a valid ModuleSpec even for nonexistent files. The source has # pragma: no cover."""
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'testdb'
    cs.provider = 'sqlite3'

    migrator = DbMigrator(cs)
    try:
        migrator._DbMigrator__load_migration('/nonexistent/path/module.py')  # type: ignore[attr-defined]
    except FileNotFoundError:
        pass


@fact
@trait('unit')
def when_apply_migrations_given_no_migrations_path__then_uses_default_path_pattern() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'mydb'
    cs.provider = 'sqlite3'

    with patch('deev.common.db_migrator.DbMigrator.apply') as mock_apply, \
            patch('deev.common.db_migrator.DbMigrator.__init__') as init_p:  # type: ignore[arg-type]
        init_p.returns(None)
        apply_migrations('all', cs, migrations_path=None)

    assert mock_apply.called


@fact
@trait('unit')
def when_apply_migrations_given_null_database_and_no_path__then_raises_ValueError() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = None  # No database

    try:
        apply_migrations('all', cs, migrations_path=None)
    except ValueError:
        pass  # expected
    else:
        raise AssertionError('Expected ValueError to be raised.')


@fact
@trait('unit')
def when_undo_migrations_given_no_migrations_path__then_uses_default_path_pattern() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'mydb'
    cs.provider = 'sqlite3'

    with patch('deev.common.db_migrator.DbMigrator.undo') as mock_undo, \
            patch('deev.common.db_migrator.DbMigrator.__init__') as init_p:  # type: ignore[arg-type]
        init_p.returns(None)
        undo_migrations('all', cs, migrations_path=None)

    assert mock_undo.called


@fact
@trait('unit')
def when_apply_migrations_with_custom_migration_name__then_passes_name_to_engine() -> None:
    cs = ConnectionString()
    cs.server = 'test'
    cs.database = 'mydb'
    cs.provider = 'sqlite3'

    with patch('deev.common.db_migrator.DbMigrator.apply') as mock_apply, \
            patch('deev.common.db_migrator.DbMigrator.__init__') as init_p:  # type: ignore[arg-type]
        init_p.returns(None)
        apply_migrations('custom_name', cs, migrations_path='/custom/path')

    assert mock_apply.calls[0].args[1] == 'custom_name'


@fact
def when_constructed_with_sqlite_test_connection__then_selects_migration_data_type_v1() -> None:
    """Uses real appsettings connection but patches DB layer — tests type-selection logic."""
    cs = _get_test_connectionstring('sqlite_test')

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    assert migrator._DbMigrator__migrationdata_t is _MigrationData  # type: ignore[attr-defined]
    _release_patches(patches)


@fact
def when_constructed_with_mysql_test_connection__then_selects_migration_data_type_v1() -> None:
    """Uses real appsettings connection but patches DB layer — tests type-selection logic."""
    cs = _get_test_connectionstring('mysql_test')

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    assert migrator._DbMigrator__migrationdata_t is _MigrationData  # type: ignore[attr-defined]
    _release_patches(patches)


@fact
def when_constructed_with_mongo_test_connection__then_selects_migration_data_type_is_v2() -> None:
    """Uses real appsettings connection but patches DB layer — tests type-selection logic."""
    cs = _get_test_connectionstring('mongo_test')

    migrator, mock_adapter, patches = _migrator_mocked(cs)
    assert migrator._DbMigrator__migrationdata_t is _MigrationData2  # type: ignore[attr-defined]
    _release_patches(patches)
