# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import TypeAlias

from .async_db_connection import AsyncDbConnection
from .async_db_transaction_context import AsyncDbTransactionContext
from .db_connection import DbConnection
from .db_transaction_context import DbTransactionContext

AsyncDbContext: TypeAlias = AsyncDbConnection | AsyncDbTransactionContext
"""Type alias for an async database context (connection or transaction)."""

DbContext: TypeAlias = DbConnection | DbTransactionContext
"""Type alias for a sync database context (connection or transaction)."""

__all__ = [
    'AsyncDbContext',
    'DbContext'
]
