# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Protocol, runtime_checkable


@runtime_checkable
class DbTypeMapper(Protocol):

    def get_sqltype(self, field_name: str) -> str:
        """
        Get the SQL type (string) needed to represent an entity field in the underlying table.

        :param field_spec: The "Entity Field Spec".
        :return: The SQL type string.
        """
        ...
