# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import final


@final
class DbError(Exception):
    """Exception raised when a DB operation fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)

    def __repr__(self) -> str:
        return (f'{self.__class__.__name__}(reason={self.reason!r})')

    def __str__(self) -> str:
        return self.__repr__()
