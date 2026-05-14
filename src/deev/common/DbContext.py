# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import TypeAlias

from .DbConnection import DbConnection
from .DbTransactionContext import DbTransactionContext

DbContext: TypeAlias = DbConnection | DbTransactionContext


__all__ = ['DbContext']
