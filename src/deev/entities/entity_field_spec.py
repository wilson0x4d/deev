# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any, Callable

from .._immutable_mixin import _ImmutableMixin
from .index_options import IndexOptions


class EntityFieldSpec(_ImmutableMixin):
    """Entity Field Specification"""

    autoincrement: bool | None  # if the field should be configured for autoincrement (applies to PK only)
    default: Callable[..., Any] | Any | None  # the field should have a default value applied on creation. may be a value or a function.
    index: IndexOptions | None  # the field is part of an index definition, this represents the index options for the field
    mapped: bool | None  # whether or not the field is mapped, fields are always mapped by default
    max: int | float | None  # maximum length <= value (validation)
    min: int | float | None  # minimum length >= value (validation)
    nullable: bool | None  # the db should support NULL values for this field
    primary_key: bool | None  # the field is part of a primary key definition
    dbtype: str | None  # dbtype override
    unique: bool | None  # the field should be unique in the table
    validator: Callable[[Any], Any] | None  # a custom validator function

    def __init__(self, **kwargs: Any) -> None:
        self.autoincrement = None
        # NOTE: we do not populate, since `None` may be the default value we are looking to set
        #       therefore, we never "enforce" a value for `default` and instead always check `hasattr`
        #       to determine the difference.
        # self.default = None
        self.index = None
        self.mapped = None
        self.max = None
        self.min = None
        self.nullable = None
        self.primary_key = None
        self.dbtype = None
        self.unique = None
        self.validator = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def sqltype(self) -> str | None:  # pragma: nocover
        # DEPRECATED: compatibility stub, remove in next major release
        return self.dbtype


__all__ = ['EntityFieldSpec']
