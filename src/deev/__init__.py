# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

"""
deev — An entity framework for Python.

Maps Python classes to database tables/collections, provides CRUD
via ``TableAdapter``s, and includes a ``db-migrate`` CLI.
"""

from __future__ import annotations

from . import clickhouse, common, entities, mongodb, mysql, translation, utils, validation
from .common.connection_string import ConnectionString
from .common.db_error import DbError
from .entities import (
    entity,
    field
)
from .translation import hydrate, splat
from .utils import connect


__version__ = '0.0.0'
__commit__ = '0abc123'
__all__ = [
    '__version__',
    '__commit__',
    'ConnectionString',
    'DbError',
    'clickhouse',
    'common',
    'connect',
    'entities',
    'entity',
    'field',
    'hydrate',
    'mongodb',
    'mysql',
    'splat',
    'translation',
    'utils',
    'validation'
]
