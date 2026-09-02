# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from enum import StrEnum


class IndexOrder(StrEnum):
    """
    Enumeration of index sort directions.
    """
    ASCENDING = 'ascending'
    DESCENDING = 'descending'


__all__ = ['IndexOrder']
