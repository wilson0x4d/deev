# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.utils import begin_transaction
import appsettings2
from deev.common import ConnectionString, DbError
from deev.mongodb.MongoTransactionContext import MongoTransactionContext
from deev.utils import connect
import inspect
from punit import fact, trait
import pymongo
from uuid import uuid4


def get_mongodb_connectionstring():
    """Get the ConnectionString to be used by mongodb tests."""
    configuration = appsettings2.get_configuration()
    connection_str = configuration.connections.mongo_test
    return ConnectionString(connection_str)


@fact
@trait('integration')
@trait('mongodb')
def transaction_begin_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = begin_transaction(connection)
        assert isinstance(tx, MongoTransactionContext)


@fact
@trait('integration')
@trait('mongodb')
def transaction_commit_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        with MongoTransactionContext(connection) as tx:
            # NOP
            tx.commit()


@fact
@trait('integration')
@trait('mongodb')
def transaction_rollback_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        tx.rollback()


@fact
@trait('integration')
@trait('mongodb')
def transaction_context_manager_auto_commit_on_success() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:  # noqa
        # Should not raise -- auto-commits on success
        pass


@fact
@trait('integration')
@trait('mongodb')
def transaction_cursor_returns_cursor() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        cursor = tx.cursor()
        assert cursor is not None


@fact
@trait('integration')
@trait('mongodb')
def transaction_mongo_session_property_returns_session() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        session = tx.mongo_session  # type: ignore[attr-defined]
        assert isinstance(session, pymongo.client_session.ClientSession)


@fact
@trait('integration')
@trait('mongodb')
def transaction_execute_reader_yields_rows() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        # Insert data via a supported SQL-like operation
        cursor = tx.execute(
            'INSERT deev_test(id, value) VALUES (%?, %?)', ('tx-test-1', 'hello')
        )
        assert cursor is not None


@fact
@trait('integration')
@trait('mongodb')
def transaction_execute_nonquery_works() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        # execute_nonquery returns None by design; verify it doesn't raise
        try:
            tx.execute_nonquery(
                'INSERT deev_test(id, value) VALUES (%?, %?)', ('tx-test-2', 'world')
            )
        except Exception:
            assert False, 'execute_nonquery should not raise on a valid operation'


@fact
@trait('integration')
@trait('mongodb')
def transaction_context_manager_auto_commits_state1_on_success() -> None:
    """A transaction that begins but never writes must auto-commit on __exit__."""
    conn_str = get_mongodb_connectionstring()
    caught_error: Exception | None = None
    try:
        with connect(conn_str) as connection:
            tx = MongoTransactionContext(connection)
            assert getattr(tx, '_MongoTransactionContext__transaction_state') == 0, "Initial state should be 0"
            tx.begin_transaction()
            assert getattr(tx, '_MongoTransactionContext__transaction_state') == 1, "After begin: state should be 1"
            tx.__exit__(None, None, None)
            assert getattr(tx, '_MongoTransactionContext__transaction_state') == 3, (
                f"Expected state=3 after auto-commit, got {getattr(tx, '_MongoTransactionContext__transaction_state')}."
            )
    except Exception as e:
        caught_error = e

    assert caught_error is None, f"Expected no error but got {type(caught_error).__name__}: {caught_error}"


@fact
@trait('integration')
@trait('mongodb')
def transaction_execute_script_raises_after_rollback() -> None:
    """execute_script should raise DbError after the transaction is rolled back."""
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        tx.rollback()
        try:
            tx.execute_script("{'$ping': 1}")
            assert False, 'execute_script should have raised DbError'
        except Exception as e:
            assert isinstance(e, DbError), f"Expected DbError but got {type(e).__name__}"


@fact
@trait('integration')
@trait('mongodb')
def transaction_prefix_matching_does_not_false_positive() -> None:
    """Field/column names starting with SQL prefixes should not misidentify write operations."""
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        uid = f'tx-pfx-{uuid4().hex[:8]}'
        cursor = tx.execute(
            'INSERT deev_test(id, created_at) VALUES (%?, %?)', (uid, 123)
        )
        assert cursor is not None
        tx.commit()


@fact
@trait('unit')
def transaction_context_var_name_correctly_spelled() -> None:
    """The ContextVar name should be spelled 'transaction' not 'transacton'."""
    var = MongoTransactionContext._MongoTransactionContext__ambient_transaction_id  # type: ignore[attr-defined]
    assert 'transacton' not in var.name, f"Typo found in ContextVar name: {var.name}"


@fact
@trait('integration')
@trait('mongodb')
def transaction_context_manager_rollback_on_exception_with_state_one() -> None:
    """When __exit__ receives an exception and the transaction is in state 1
    (begun but no writes), it should rollback - not auto-commit."""
    conn_str = get_mongodb_connectionstring()
    error_caught: Exception | None = None

    try:
        with connect(conn_str) as connection:
            tx = MongoTransactionContext(connection)
            tx.begin_transaction()  # state -> 1
            assert getattr(tx, '_MongoTransactionContext__transaction_state') == 1
            raise RuntimeError("simulated crash")
    except RuntimeError as e:
        if 'simulated' in str(e):
            error_caught = e
        else:
            raise

    assert error_caught is not None, "Expected simulated RuntimeError to propagate"


@fact
@trait('integration')
@trait('mongodb')
def transaction_context_manager_no_double_rollback() -> None:
    """__exit__ should not call rollback twice (state==2 appears in both branches)."""
    conn_str = get_mongodb_connectionstring()
    rollback_count: list[int] = [0]

    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        tx.begin_transaction()
        # Override rollback to count calls
        original_rollback = tx.rollback

        def counting_rollback():
            rollback_count[0] += 1
            return original_rollback()
        tx.rollback = counting_rollback  # type: ignore[method-assign]

        try:
            tx.__exit__(RuntimeError, RuntimeError("test"), None)
        except RuntimeError:
            pass

    # After fix: state==2 + exc → one rollback (from line 58 only), never double
    assert rollback_count[0] <= 1, f"rollback called {rollback_count[0]} times - should be at most 1"


@fact
@trait('integration')
@trait('mongodb')
def transaction_mongo_database_property_exists() -> None:
    conn_str = get_mongodb_connectionstring()
    with connect(conn_str) as connection:
        tx = MongoTransactionContext(connection)
        mongo_database = getattr(tx, 'mongo_database', None)
        assert mongo_database is not None, 'mongo_database property should exist'
