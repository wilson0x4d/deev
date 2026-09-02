# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field as dc_field

from .index_order import IndexOrder


@dataclass(frozen=True)
class IndexOptions:
    """
    Configuration for a database index on an entity field.

    Usage
    -----

    .. code-block:: python

        IndexOptions(
            name="idx_users_email",
            direction=IndexOrder.ASCENDING,
            rank=0,
            type=None
        )

    :param name: Unique name for the index.
    :param direction: Sort direction (``ASCENDING`` or ``DESCENDING``).
    :param rank: Ordering rank when multiple fields share the same index name.
    :param type: Index type for skip indexes (ClickHouse).
    """

    name: str
    direction: IndexOrder = dc_field(default=IndexOrder.ASCENDING)
    rank: int = dc_field(default=0)
    type: str | None = dc_field(default=None)


__all__ = ['IndexOptions']
