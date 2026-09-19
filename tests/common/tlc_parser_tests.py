# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

"""Tests for the transaction-control SQL parser module."""

from punit import fact, trait

from deev.common.tlc_parser import (
    extract_begin_name,
    extract_rollback_name,
    extract_savepoint_name,
    is_rollback_to,
)


# --- extract_begin_name tests ---


@fact
@trait('common')
def begin_transaction_name_extracted() -> None:
    assert extract_begin_name('BEGIN TRANSACTION my_txn') == 'my_txn'


@fact
@trait('common')
def begin_trans_name_extracted() -> None:
    assert extract_begin_name('BEGIN TRAN my_txn') == 'my_txn'


@fact
@trait('common')
def begin_transaction_no_name_returns_none() -> None:
    assert extract_begin_name('BEGIN TRANSACTION') is None


@fact
@trait('common')
def begin_no_name_returns_none() -> None:
    assert extract_begin_name('BEGIN') is None


@fact
@trait('common')
def begin_case_insensitive_keyword_preserves_name_case() -> None:
    assert extract_begin_name('begin transaction MySavePoint') == 'MySavePoint'


@fact
@trait('common')
def begin_leading_whitespace_stripped() -> None:
    assert extract_begin_name('  BEGIN TRANSACTION my_txn') == 'my_txn'


@fact
@trait('common')
def begin_multiple_spaces_between_tokens() -> None:
    assert extract_begin_name('BEGIN  TRANSACTION   my_txn') == 'my_txn'


@fact
@trait('common')
def begin_mixed_case_keyword() -> None:
    assert extract_begin_name('BeGiN TrAnSaCtIoN my_txn') == 'my_txn'


# --- extract_savepoint_name tests ---


@fact
@trait('common')
def savepoint_name_extracted() -> None:
    assert extract_savepoint_name('SAVEPOINT my_sp') == 'my_sp'


@fact
@trait('common')
def save_transaction_name_extracted() -> None:
    assert extract_savepoint_name('SAVE TRANSACTION my_sp') == 'my_sp'


@fact
@trait('common')
def save_tran_name_extracted() -> None:
    assert extract_savepoint_name('SAVE TRAN my_sp') == 'my_sp'


@fact
@trait('common')
def savepoint_no_name_returns_none() -> None:
    assert extract_savepoint_name('SAVEPOINT') is None


@fact
@trait('common')
def save_transaction_no_name_returns_none() -> None:
    assert extract_savepoint_name('SAVE TRANSACTION') is None


@fact
@trait('common')
def savepoint_case_insensitive_keyword_preserves_name_case() -> None:
    assert extract_savepoint_name('savepoint MySavePoint') == 'MySavePoint'


@fact
@trait('common')
def savepoint_leading_whitespace_stripped() -> None:
    assert extract_savepoint_name('  SAVEPOINT my_sp') == 'my_sp'


@fact
@trait('common')
def savepoint_multiple_spaces() -> None:
    assert extract_savepoint_name('SAVEPOINT   my_sp') == 'my_sp'


# --- extract_rollback_name tests ---


@fact
@trait('common')
def rollback_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK my_txn') == 'my_txn'


@fact
@trait('common')
def rollback_transaction_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TRANSACTION my_txn') == 'my_txn'


@fact
@trait('common')
def rollback_to_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TO my_sp') == 'my_sp'


@fact
@trait('common')
def rollback_to_savepoint_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TO SAVEPOINT my_sp') == 'my_sp'


@fact
@trait('common')
def rollback_to_transaction_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TO TRANSACTION my_txn') == 'my_txn'


@fact
@trait('common')
def rollback_to_savepoint_transaction_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TO SAVEPOINT TRANSACTION my_sp') == 'my_sp'


@fact
@trait('common')
def rollback_trans_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TRAN my_txn') == 'my_txn'


@fact
@trait('common')
def rollback_to_trans_name_extracted() -> None:
    assert extract_rollback_name('ROLLBACK TO TRAN my_txn') == 'my_txn'


@fact
@trait('common')
def rollback_no_name_returns_none() -> None:
    assert extract_rollback_name('ROLLBACK') is None


@fact
@trait('common')
def rollback_nothing_returns_none() -> None:
    assert extract_rollback_name('') is None


@fact
@trait('common')
def rollback_leading_whitespace_stripped() -> None:
    assert extract_rollback_name('  ROLLBACK my_txn') == 'my_txn'


@fact
@trait('common')
def rollback_case_insensitive_keyword_preserves_name_case() -> None:
    assert extract_rollback_name('rollback transaction MyName') == 'MyName'


# --- is_rollback_to tests ---


@fact
@trait('common')
def rollback_to_savepoint_is_detected() -> None:
    assert is_rollback_to('ROLLBACK TO SAVEPOINT my_sp') is True


@fact
@trait('common')
def rollback_to_transaction_is_detected() -> None:
    assert is_rollback_to('ROLLBACK TO TRANSACTION my_txn') is True


@fact
@trait('common')
def rollback_to_name_is_detected() -> None:
    assert is_rollback_to('ROLLBACK TO my_sp') is True


@fact
@trait('common')
def rollback_to_trans_is_detected() -> None:
    assert is_rollback_to('ROLLBACK TO TRAN my_txn') is True


@fact
@trait('common')
def rollback_name_only_not_detected() -> None:
    assert is_rollback_to('ROLLBACK my_txn') is False


@fact
@trait('common')
def rollback_transaction_not_detected() -> None:
    assert is_rollback_to('ROLLBACK TRANSACTION my_txn') is False


@fact
@trait('common')
def rollback_only_not_detected() -> None:
    assert is_rollback_to('ROLLBACK') is False


@fact
@trait('common')
def rollback_to_leading_whitespace_stripped() -> None:
    assert is_rollback_to('  ROLLBACK TO my_sp') is True


@fact
@trait('common')
def rollback_to_case_insensitive() -> None:
    assert is_rollback_to('rollback to my_sp') is True
