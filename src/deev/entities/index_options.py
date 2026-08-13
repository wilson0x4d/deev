# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field as dc_field

from .index_order import IndexOrder


@dataclass(frozen=True)
class IndexOptions:

    name: str
    direction: IndexOrder = dc_field(default=IndexOrder.ASCENDING)
    rank: int = dc_field(default=0)
    type: str | None = dc_field(default=None)


__all__ = ['IndexOptions']
