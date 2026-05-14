# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any, TypeAlias

DbParams: TypeAlias = tuple[Any, ...] | list[Any] | dict[str, Any]


__all__ = ['DbParams']
