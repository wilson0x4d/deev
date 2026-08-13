# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import TypeAlias

from .async_db_connection import AsyncDbConnection
from .async_db_transaction_context import AsyncDbTransactionContext
from .db_connection import DbConnection
from .db_transaction_context import DbTransactionContext

AsyncDbContext: TypeAlias = AsyncDbConnection | AsyncDbTransactionContext
DbContext: TypeAlias = DbConnection | DbTransactionContext

__all__ = [
    'AsyncDbContext',
    'DbContext'
]
