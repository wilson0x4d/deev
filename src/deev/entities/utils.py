# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from decimal import Decimal
import inspect
import re
from types import NoneType, UnionType
from typing import (
    Any,
    Callable,
    Mapping,
    Type,
    TypeVar,
    Union,
    cast,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints
)

from .entity_field_spec import EntityFieldSpec
from .entity_spec import EntitySpec
from .index_options import IndexOptions
from .index_order import IndexOrder


T = TypeVar('T')
__NOTSET__ = object()


def snake_case_name(s: str) -> str:
    """Convert a string to snake_case."""
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
    return s.lower().strip('_')


def pluralize(name: str, snake_case: bool = False) -> str:
    """
    Derive a plural form of *name* using simple English rules.

    If the name already appears plural (ends with 's'), it is returned unchanged.

    :param name: The singular name to pluralize.
    :param snake_case: If ``True``, convert to snake_case before pluralizing.
    :return: The pluralized name.
    """
    if not name:
        return name
    if snake_case is True:
        name = snake_case_name(name)
    if name.endswith('s'):
        return name
    if name.endswith(('x', 'z', 'ch', 'sh')):
        return name + 'es'
    if name.endswith('y') and len(name) > 1 and name[-2].lower() not in 'aeiou':
        return name[:-1] + 'ies'
    return name + 's'


def define_entity_spec(
    entity_type: type,
    *,
    table_name: str | None = None,
    no_pluralization: bool = False,
    snake_case: bool = False,
    **kwargs: Any
) -> EntitySpec:
    """
    Define or retrieve the entity spec for a class.

    If the spec already exists on the class (via :func:`entity` decorator), returns it.
    Otherwise, creates a new :class:`EntitySpec` by introspecting the class type hints
    and field values, then caches it on the class.

    :param entity_type: The entity class.
    :param table_name: Optional explicit table name override.
    :param no_pluralization: If ``True``, use the class name directly without pluralization.
    :param snake_case: If ``True``, convert class name to snake_case before pluralizing.
    :param kwargs: Additional spec options stored in :attr:`EntitySpec.extra_args`.
    :return: The :class:`EntitySpec` for the class (cached on the class).
    :raises DbError: If the class has complex Union types not supported.
    """
    entity_spec = getattr(entity_type, '__deev_entity__', None)
    if entity_spec is None:
        has_autoincrement = False
        attrs = get_type_hints(entity_type)
        fields = dict[str, EntityFieldSpec]()
        primary_key = list[str]()
        for attr_name, attr_type in attrs.items():
            is_union_type = get_origin(attr_type) in (Union, UnionType)
            attr_type_args = tuple() if not is_union_type else get_args(attr_type)
            is_nullable_implied = is_union_type and (NoneType in attr_type_args)
            is_unsupported_union = is_union_type and (len(attr_type_args) > 2 or not is_nullable_implied)
            if is_unsupported_union:
                from ..common import DbError
                raise DbError(f'Invalid typing for field "{attr_name}", complex Unions are not supported."')
            attr_value = getattr(entity_type, attr_name, __NOTSET__)
            field_spec: EntityFieldSpec
            if isinstance(attr_value, EntityFieldSpec):
                field_spec = attr_value
                if field_spec.nullable is None and is_nullable_implied:
                    field_spec.nullable = True
            else:
                field_spec = EntityFieldSpec(
                    nullable=is_nullable_implied
                )
                if attr_value is not __NOTSET__:
                    field_spec.default = attr_value
            fields[attr_name] = field_spec
            if field_spec.primary_key is True:
                primary_key.append(attr_name)
                if field_spec.autoincrement:
                    has_autoincrement = True
            field_spec.__freeze__()
        entity_spec = EntitySpec(
            attrs=(attrs if attrs is not None else {}),
            entity_type=entity_type,
            fields=fields,
            has_autoincrement=has_autoincrement,
            primary_key=tuple(primary_key),
            table_name=(
                table_name
                if table_name is not None
                else (
                    pluralize(entity_type.__name__, snake_case=snake_case)
                    if no_pluralization is False
                    else (
                        entity_type.__name__
                        if snake_case is False
                        else snake_case_name(entity_type.__name__)
                    )
                )
            ),
            **kwargs
        )
        setattr(entity_type, '__deev_entity__', entity_spec.__freeze__())
    return entity_spec


def get_entity_spec(entity_type: type) -> EntitySpec:
    """
    Get the entity spec for *entity_type*.

    If not yet defined, it will be created by calling :func:`define_entity_spec`.

    :param entity_type: The entity class.
    :return: The :class:`EntitySpec` for the class.
    """
    entity_spec = getattr(entity_type, '__deev_entity__', None)
    if entity_spec is None:
        return define_entity_spec(entity_type)
    else:
        return entity_spec


def field(
    *,
    autoincrement: bool | None = None,
    default: Callable[..., Any] | Any | None = __NOTSET__,
    index: str | IndexOptions | None = None,
    mapped: bool | None = None,
    max: int | float | Decimal | None = None,
    min: int | float | Decimal | None = None,
    nullable: bool | None = None,
    primary_key: bool | None = None,
    dbtype: str | None = None,
    unique: bool | None = None,
    validator: Callable[[Any], Any] | None = None,
    init: bool = True
) -> Any:
    """
    Create an :class:`EntityFieldSpec` for use as a class attribute.

    The returned spec is used by :func:`entity` decorator to define the database
    column mapping, constraints, and indexing for the field.

    :param autoincrement: Whether the primary key field should auto-increment.
    :param default: Default value or zero-argument callable. Uses sentinel to distinguish "not set" from ``None``.
    :param index: Index name or :class:`IndexOptions` defining the index field.
    :param mapped: If ``False``, the field is excluded from SQL translation.
    :param max: Maximum value or maximum string length (for validation).
    :param min: Minimum value or minimum string length (for validation).
    :param nullable: Whether the database column allows NULL values. Auto-inferred from ``Optional[...]``.
    :param primary_key: Whether this field is part of the primary key.
    :param dbtype: Override the auto-detected database column type.
    :param unique: Whether values in this column must be unique.
    :param validator: Custom validator function that returns ``ValidationError | None``.
    :param init: If ``True``, the field participates in ``__init__``. Default ``True``.
    :return: An :class:`EntityFieldSpec` instance.
    """
    # TODO: validation, ie min >= max, autoincrement only valid for integer+pk fields, etc/etc
    if isinstance(index, str):
        index = IndexOptions(name=index, direction=IndexOrder.ASCENDING, rank=0)
    field_spec = EntityFieldSpec(
        autoincrement=autoincrement,
        index=index,
        mapped=mapped,
        max=max,
        min=min,
        nullable=nullable,
        primary_key=primary_key,
        dbtype=dbtype,
        unique=unique,
        validator=validator
    )
    if default is not __NOTSET__:
        setattr(field_spec, 'default', default)
    return field_spec


def __can_kwarg(func: Callable[..., Any], kwargs: Mapping[str, Any]) -> bool:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover
        return False
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


@dataclass_transform(eq_default=False, order_default=False, field_specifiers=(field,))
def entity(
    cls: Type[T] | None = None,
    *,
    table_name: str | None = None,
    no_pluralization: bool = False,
    defer_init: bool = False,
    snake_case: bool = False,
    **kwargs: Any
) -> Any:
    """
    Transform a "simple" class definition into an "Entity" class.

    Applies field defaults, hides :class:`EntityFieldSpec` attributes from attribute access,
    and generates an ``__init__`` that applies default values before calling the original ``__init__``.

    :param cls: The class to decorate.
    :param table_name: Optional explicit table name override.
    :param no_pluralization: If ``True``, do not pluralize the class name for the table name.
    :param defer_init: If ``True``, call original ``__init__`` before applying field defaults (useful for mixin base classes).
    :param snake_case: If ``True``, convert class name to snake_case before pluralizing for table name.
    :param kwargs: Additional options stored in :attr:`EntitySpec.extra_args`.
    :return: The decorated class with entity capabilities.
    """
    if cls is None:
        def __entity(_cls: Type[T]) -> Type[T]:
            return entity(_cls, table_name=table_name, no_pluralization=no_pluralization, defer_init=defer_init, snake_case=snake_case, **kwargs)  # type: ignore[bad-return]
        return __entity  # type: ignore[return-value]
    else:
        L_init = None if not hasattr(cls, '__init__') else cast(Callable[..., Any], cls.__init__)
        entity_spec = define_entity_spec(cls, table_name=table_name, no_pluralization=no_pluralization, snake_case=snake_case, **kwargs)

        def hide_fieldspec(self: Any, name: str) -> Any:
            v = object.__getattribute__(self, name)
            if self is not None:
                if isinstance(v, EntityFieldSpec):
                    raise AttributeError(name)
                elif v in (NoneType, None):
                    field_spec = entity_spec.fields.get(name)
                    if field_spec.nullable is not True:  # type: ignore[union-attr]  # because we know it's present
                        # NOTE: unless explicitly spec'd nullable, hide None/NoneType assignments
                        raise AttributeError(name)
            return v
        setattr(cls, '__getattribute__', hide_fieldspec)

        if defer_init:
            def init(*args: Any, **kwargs: Any) -> None:
                self = args[0]
                if L_init is not None:
                    if L_init is object.__init__:
                        L_init(self)
                    elif len(kwargs) > 0 and __can_kwarg(L_init, kwargs):
                        L_init(*args, **kwargs)
                    else:
                        L_init(*args)
                for field_name, field_spec in entity_spec.fields.items():
                    if hasattr(field_spec, 'default'):
                        if field_spec.default is not None and callable(field_spec.default):
                            setattr(self, field_name, field_spec.default())
                        else:
                            setattr(self, field_name, field_spec.default)
                if kwargs is not None:
                    for k, v in kwargs.items():
                        setattr(self, k, v)
        else:
            def init(*args: Any, **kwargs: Any) -> None:
                self = args[0]
                for field_name, field_spec in entity_spec.fields.items():
                    if hasattr(field_spec, 'default'):
                        if field_spec.default is not None and callable(field_spec.default):
                            setattr(self, field_name, field_spec.default())
                        else:
                            setattr(self, field_name, field_spec.default)
                if L_init is not None:
                    if L_init is object.__init__:
                        L_init(self)
                    elif len(kwargs) > 0 and __can_kwarg(L_init, kwargs):
                        L_init(*args, **kwargs)
                    else:
                        L_init(*args)
                if kwargs is not None:
                    for k, v in kwargs.items():
                        setattr(self, k, v)

        setattr(cls, '__init__', init)
        return cls


__all__ = [
    'define_entity_spec',
    'entity',
    'field',
    'get_entity_spec',
    'pluralize',
]
