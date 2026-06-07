# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

try:
    from .MongoProxyConnection import MongoProxyConnection
    from .MongoProxyCursor import MongoProxyCursor
    from .MongoTableAdapter import MongoTableAdapter
    from .MongoTransactionContext import MongoTransactionContext
    from .MongoTypeMapper import MongoTypeMapper
except Exception:
    # NOTE: if required packages are not installed we expect this module to import without errors
    pass


__all__ = [
    'MongoProxyConnection',
    'MongoProxyCursor',
    'MongoTableAdapter',
    'MongoTransactionContext',
    'MongoTypeMapper'
]
