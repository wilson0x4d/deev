# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import TypeAlias

from .db_connection import DbConnection
from .db_transaction_context import DbTransactionContext

DbContext: TypeAlias = DbConnection | DbTransactionContext


__all__ = ['DbContext']
