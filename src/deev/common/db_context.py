# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import TypeAlias

from .async_db_connection import AsyncDbConnection
from .async_db_transaction_context import AsyncDbTransactionContext
from .db_connection import DbConnection
from .db_transaction_context import DbTransactionContext

AsyncDbContext: TypeAlias = AsyncDbConnection | AsyncDbTransactionContext
"""
Type alias for an async database context: an open connection or a transaction,
allowing logic to apply to both. Unrelated to :class:`AsyncDbAdapter`, which
is a class-based adapter grouping table adapters for a single database.
"""

DbContext: TypeAlias = DbConnection | DbTransactionContext
"""
Type alias for a sync database context: an open connection or a transaction,
allowing logic to apply to both. Unrelated to :class:`DbAdapter`, which is a
class-based adapter grouping table adapters for a single database.
"""

__all__ = [
    'AsyncDbContext',
    'DbContext'
]
