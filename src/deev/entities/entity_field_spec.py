# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from typing import Any, Callable, Optional

from .._immutable_mixin import _ImmutableMixin
from .index_options import IndexOptions


class EntityFieldSpec(_ImmutableMixin):
    """Entity Field Specification"""

    autoincrement: Optional[bool]  # if the field should be configured for autoincrement (applies to PK only)
    default: Optional[Callable[..., Any] | Any]  # the field should have a default value applied on creation. may be a value or a function.
    index: Optional[IndexOptions]  # the field is part of an index definition, this represents the index options for the field
    mapped: Optional[bool]  # whether or not the field is mapped, fields are always mapped by default
    max: Optional[int | float]  # maximum length <= value (validation)
    min: Optional[int | float]  # minimum length >= value (validation)
    nullable: Optional[bool]  # the db should support NULL values for this field
    primary_key: Optional[bool]  # the field is part of a primary key definition
    dbtype: Optional[str]  # dbtype override
    unique: Optional[bool]  # the field should be unique in the table
    validator: Optional[Callable[[Any], Any]]  # a custom validator function

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
    def sqltype(self) -> Optional[str]:  # pragma: nocover
        # DEPRECATED: compatibility stub, remove in next major release
        return self.dbtype


__all__ = ['EntityFieldSpec']
