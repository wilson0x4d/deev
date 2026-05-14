# SPDX-FileCopyrightText: © 2025 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any


class _ImmutableMixin:
    """Mixin that adds a ``freeze`` operation."""
    __frozen__: bool = False

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, '__frozen__', False):
            raise AttributeError(f'Cannot modify frozen instance: {name}')
        # Call ``super()`` so the next class in the MRO (e.g. BaseModel) can run
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, '__frozen__', False):
            raise AttributeError(f'Cannot delete attribute from frozen instance: {name}')
        super().__delattr__(name)

    def __freeze__(self) -> Any:
        """Mark the instance as immutable."""
        object.__setattr__(self, '__frozen__', True)
        return self


__all__ = ['_ImmutableMixin']
