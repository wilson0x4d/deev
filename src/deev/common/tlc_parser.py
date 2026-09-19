# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

"""Transaction-control SQL keyword detection and name extraction.

Provides regex-based parsers for transaction-control (TLC) SQL statements.
Names are extracted from the original-case SQL, preserving the case used
by the caller.
"""

from __future__ import annotations

import re

_BEGIN_PATTERN = re.compile(
    r'^BEGIN\s+(?:TRANSACTION|TRAN)\s+(\S+)',
    re.IGNORECASE,
)

_SAVEPOINT_PATTERN = re.compile(
    r'^(?:SAVEPOINT|SAVE\s+(?:TRANSACTION|TRAN))\s+(\S+)',
    re.IGNORECASE,
)

# Handles: ROLLBACK name, ROLLBACK TO name, ROLLBACK TO SAVEPOINT name,
#          ROLLBACK TRANSACTION name, ROLLBACK TO TRANSACTION name, etc.
# Uses a multi-step parser instead of a single regex to avoid
# backtracking issues with optional keyword groups.

_ROLLBACK_TO_PREFIX = re.compile(
    r'^ROLLBACK\s+TO\s',
    re.IGNORECASE,
)


def extract_begin_name(sql: str) -> str | None:
    """Extract the transaction name from a ``BEGIN [TRANSACTION|TRAN] name`` statement.

    Returns the name exactly as written in the original SQL, or ``None`` if no
    name is present.
    """
    m = _BEGIN_PATTERN.match(sql.lstrip())
    return m.group(1) if m else None


def extract_savepoint_name(sql: str) -> str | None:
    """Extract the savepoint name from a ``SAVEPOINT name`` or ``SAVE [TRANSACTION|TRAN] name`` statement.

    Returns the name exactly as written in the original SQL, or ``None`` if no
    name is present.
    """
    m = _SAVEPOINT_PATTERN.match(sql.lstrip())
    return m.group(1) if m else None


def extract_rollback_name(sql: str) -> str | None:
    """Extract the name from a ``ROLLBACK [TO [SAVEPOINT|TRANSACTION|TRAN]] name`` statement.

    Returns the name exactly as written in the original SQL, or ``None`` if no
    name is present.
    """
    s = sql.lstrip()
    if not s.upper().startswith('ROLLBACK'):
        return None
    rest = s[8:].lstrip()

    # Skip optional "TO"
    if rest.upper().startswith('TO '):
        rest = rest[3:].lstrip()

    # Skip optional "SAVEPOINT"
    if rest.upper().startswith('SAVEPOINT'):
        rest = rest[9:].lstrip()
    # Skip optional "TRANSACTION" or "TRAN"
    if rest.upper().startswith('TRANSACTION'):
        rest = rest[11:].lstrip()
    elif rest.upper().startswith('TRAN '):
        rest = rest[5:].lstrip()

    # Extract name
    name = rest.split()[0] if rest else None
    return name


def is_rollback_to(sql: str) -> bool:
    """Return ``True`` when *sql* is a ``ROLLBACK TO ...`` statement.

    This detects the ``TO`` keyword after ``ROLLBACK`` regardless of whether
    a ``SAVEPOINT`` or ``TRANSACTION`` keyword follows it.
    """
    return _ROLLBACK_TO_PREFIX.match(sql.lstrip()) is not None


__all__ = [
    'extract_begin_name',
    'extract_savepoint_name',
    'extract_rollback_name',
    'is_rollback_to'
]
