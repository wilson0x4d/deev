# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

try:
    from .async_mongo_proxy_connection import AsyncMongoProxyConnection
    from .async_mongo_proxy_cursor import AsyncMongoProxyCursor
    from .async_mongo_table_adapter import AsyncMongoTableAdapter
    from .async_mongo_transaction_context import AsyncMongoTransactionContext
    from .mongo_proxy_connection import MongoProxyConnection
    from .mongo_proxy_cursor import MongoProxyCursor
    from .mongo_table_adapter import MongoTableAdapter
    from .mongo_transaction_context import MongoTransactionContext
    from .mongo_type_mapper import MongoTypeMapper
except Exception:
    # NOTE: if required packages are not installed we expect this module to import without errors
    pass


__all__ = [
    'AsyncMongoProxyConnection',
    'AsyncMongoProxyCursor',
    'AsyncMongoTableAdapter',
    'AsyncMongoTransactionContext',
    'MongoProxyConnection',
    'MongoProxyCursor',
    'MongoTableAdapter',
    'MongoTransactionContext',
    'MongoTypeMapper'
]
