# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from .entities import entity, field


@entity(table_name='_migrationdata')
class _MigrationData:  # type: ignore[misc]
    """Internal entity representation of ``_migrationdata`` tables used by ``deev``."""
    id: int = field(
        autoincrement=True,
        primary_key=True
    )
    migration: str = field(
        max=260,
        sqltype='VARCVHAR(260)'
    )


__all__ = ['_MigrationData']
