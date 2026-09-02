# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any, TypeAlias

DbParams: TypeAlias = tuple[Any, ...] | list[Any] | dict[str, Any]
"""Type alias for database query parameters: a tuple, list, or dict of values."""


__all__ = ['DbParams']
