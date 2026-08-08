# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from enum import StrEnum


class IndexOrder(StrEnum):
    ASCENDING = 'ascending'
    DESCENDING = 'descending'


__all__ = ['IndexOrder']
