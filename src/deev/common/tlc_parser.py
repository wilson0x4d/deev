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

_START_PATTERN = re.compile(
    r'^START\s+TRANSACTION\s+(\S+)',
    re.IGNORECASE,
)

_SAVEPOINT_PATTERN = re.compile(
    r'^(?:SAVEPOINT|SAVE\s+(?:TRANSACTION|TRAN))\s+(\S+)',
    re.IGNORECASE,
)

# Handles: ROLLBACK name, ROLLBACK TO name, ROLLBACK TO SAVEPOINT name,
#          ROLLBACK TRANSACTION name, ROLLBACK TO TRANSACTION name, etc.
# All valid syntaxes are enumerated as explicit alternations so the regex
# engine never backtracks into capturing bare keywords as names.
_ROLLBACK_TO_PREFIX = re.compile(
    r'^ROLLBACK\s+TO\s',
    re.IGNORECASE,
)

# Each alternative requires a name; alternatives that match return the
# captured group. Nothing else matches, so bare keywords return None.
_ROLLBACK_PATTERN = re.compile(
    r'^ROLLBACK\s+'
    r'(?:'
    r'TO\s+SAVEPOINT\s+TRAN(?=\s|$)\s+(\S+)'             # ROLLBACK TO SAVEPOINT TRAN name
    r'|TO\s+SAVEPOINT\s+TRANSACTION\s+(\S+)'              # ROLLBACK TO SAVEPOINT TRANSACTION name
    r'|TO\s+SAVEPOINT\s+(\S+)'                             # ROLLBACK TO SAVEPOINT name
    r'|TO\s+TRANSACTION\s+(\S+)'                           # ROLLBACK TO TRANSACTION name
    r'|TO\s+TRAN(?=\s|$)\s+(\S+)'                          # ROLLBACK TO TRAN name
    r'|TO\s+(?!SAVEPOINT\s*$|TRAN\s*$|TRANSACTION\s*$)(\S+)'  # ROLLBACK TO name
    r'|TRANSACTION\s+(\S+)'                                # ROLLBACK TRANSACTION name
    r'|TRAN(?=\s|$)\s+(\S+)'                               # ROLLBACK TRAN name
    # Reject bare keywords and TO-prefixed bare keywords
    r'|(?!SAVEPOINT\s*$|TRANSACTION\s*$|TRAN\s*$'
    r'|TO\s+(?:SAVEPOINT|TRAN|TRANSACTION)\s*$'           # TO SAVEPOINT, TO TRAN, TO TRANSACTION
    r'|TO\s*$)'                                            # bare TO
    r'\s*(\S+)'                                            # ROLLBACK name
    r')',
    re.IGNORECASE,
)


def extract_begin_name(sql: str) -> str | None:
    """Extract the transaction name from a ``BEGIN [TRANSACTION|TRAN] name`` statement.

    Returns the name exactly as written in the original SQL, or ``None`` if no
    name is present.
    """
    m = _BEGIN_PATTERN.match(sql.lstrip())
    return m.group(1) if m else None


def extract_start_name(sql: str) -> str | None:
    """Extract the transaction name from a ``START TRANSACTION name`` statement.

    Returns the name exactly as written in the original SQL, or ``None`` if no
    name is present.
    """
    m = _START_PATTERN.match(sql.lstrip())
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
    m = _ROLLBACK_PATTERN.match(sql.lstrip())
    if m is None:
        return None
    for group in m.groups():
        if group is not None:
            return group
    return None


def is_rollback_to(sql: str) -> bool:
    """Return ``True`` when *sql* is a ``ROLLBACK TO ...`` statement.

    This detects the ``TO`` keyword after ``ROLLBACK`` regardless of whether
    a ``SAVEPOINT`` or ``TRANSACTION`` keyword follows it.
    """
    return _ROLLBACK_TO_PREFIX.match(sql.lstrip()) is not None


__all__ = [
    'extract_begin_name',
    'extract_start_name',
    'extract_savepoint_name',
    'extract_rollback_name',
    'is_rollback_to'
]
