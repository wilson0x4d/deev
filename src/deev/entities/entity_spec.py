# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any, Mapping

from .._immutable_mixin import _ImmutableMixin
from .entity_field_spec import EntityFieldSpec


class EntitySpec(_ImmutableMixin):
    """
    Specification for an entity class, including its fields, table name, and metadata.

    Usage
    -----

    .. code-block:: python

        from deev.entities import get_entity_spec

        spec = get_entity_spec(User)
        print(spec.table_name)  # 'users'
        print(spec.primary_key) # ('id',)
        for field_name, field_spec in spec.fields.items():
            print(field_name, field_spec.nullable)
    """

    attrs: Mapping[str, Any]
    entity_type: type
    fields: Mapping[str, EntityFieldSpec]
    has_autoincrement: bool
    primary_key: tuple[str, ...]
    table_name: str
    extra_args: dict[str, Any]

    def __init__(
        self,
        attrs: Mapping[str, Any],
        entity_type: type,
        fields: Mapping[str, EntityFieldSpec],
        has_autoincrement: bool,
        primary_key: tuple[str, ...],
        table_name: str,
        **kwargs: Any
    ) -> None:
        """
        Initialize the EntitySpec.

        :param attrs: Type hints for the entity class fields.
        :param entity_type: The entity class itself.
        :param fields: Mapping of field names to :class:`EntityFieldSpec`.
        :param has_autoincrement: Whether the entity has an auto-increment field.
        :param primary_key: Tuple of primary key field names.
        :param table_name: The database table name.
        :param kwargs: Extra arguments stored in :attr:`extra_args`.
        """
        self.attrs = attrs
        self.entity_type = entity_type
        self.fields = fields
        self.has_autoincrement = has_autoincrement
        self.primary_key = primary_key
        self.table_name = table_name
        self.extra_args = kwargs


__all__ = ['EntitySpec']
