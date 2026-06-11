# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import uuid

from .entities import entity, field


@entity(table_name='_migrationdata')
class _MigrationData:  # type: ignore[misc]
    """Internal entity representation of ``_migrationdata`` tables used by ``deev``."""

    migration: str = field(max=260)
    id: int = field(autoincrement=True, primary_key=True)


@entity(table_name='_migrationdata')
class _MigrationData2:  # type: ignore[misc]
    """
    Internal entity representation of ``_migrationdata`` tables used by ``deev``.

    NOTE: This variant is for systems that do not support autoincrement.
    """

    migration: str = field(max=260)
    key: uuid.UUID = field(default=uuid.uuid4, primary_key=True)


__all__ = [
    '_MigrationData',
    '_MigrationData2'
]
