# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from types import MappingProxyType
from typing import Any, Mapping

from .._immutable_mixin import _ImmutableMixin
from .entity_field_spec import EntityFieldSpec


class EntitySpec(_ImmutableMixin):
    """Entity Specification"""

    attrs: Mapping[str, Any]
    entity_type: type
    fields: Mapping[str, EntityFieldSpec]
    has_autoincrement: bool
    primary_key: tuple[str, ...]
    table_name: str

    def __init__(
        self,
        attrs: Mapping[str, Any],
        entity_type: type,
        fields: Mapping[str, EntityFieldSpec],
        has_autoincrement: bool,
        primary_key: tuple[str, ...],
        table_name: str
    ) -> None:
        self.attrs = attrs
        self.entity_type = entity_type
        self.fields = fields
        self.has_autoincrement = has_autoincrement
        self.primary_key = primary_key
        self.table_name = table_name


__all__ = ['EntitySpec']
