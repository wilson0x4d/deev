# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import final


@final
class ValidationError(Exception):
    """Exception raised when a value fails validation for a specific field."""

    def __init__(self, field_name: str, reason: str) -> None:
        """
        Initialize with a field name and error reason.

        :param field_name: The field that failed validation.
        :param reason: A description of the validation failure.
        """
        self.field_name = field_name
        self.reason = reason
        super().__init__(f'Validation error on {field_name}: {reason}')

    def __repr__(self) -> str:
        return (f'{self.__class__.__name__}(field_name={self.field_name!r}, reason={self.reason!r})')

    def __str__(self) -> str:
        return f'Validation error on {self.field_name}: {self.reason}'
