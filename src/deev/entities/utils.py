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
    Sequence,
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


def construct_entity(entity_type: type, default_names: Sequence[str] | None = None) -> Any:
    """
    Construct an entity instance, applying precomputed field defaults.

    This is the fast path used by table adapters during row hydration.  When
    the class was transformed by :func:`entity` without a custom ``__init__``,
    field defaults are precomputed at decoration time and applied here
    directly, bypassing the generated ``__init__`` entirely.

    :param entity_type: The entity class to construct.
    :param default_names: The field names for which defaults should be applied.
        ``None`` applies all defaults; an empty sequence applies none.  Classes
        without precomputed defaults (e.g. a custom ``__init__`` is defined, or
        the class is not an entity) are constructed normally via
        ``entity_type()``, which applies its own defaults.
    :return: The constructed entity instance.
    """
    defaults = getattr(entity_type, '__deev_defaults__', None)
    if defaults is None:
        return entity_type()
    instance: Any = object.__new__(entity_type)
    if default_names is None:
        for name, factory in defaults:
            object.__setattr__(instance, name, factory())
    elif default_names:
        for name, factory in defaults:
            if name in default_names:
                object.__setattr__(instance, name, factory())
    return instance


def apply_defaults_for(entity: Any, default_names: Sequence[str]) -> None:
    """
    Apply precomputed field defaults to an already-constructed entity instance.

    Fields without a precomputed default are left untouched.  Instances whose
    class has no precomputed defaults are left unchanged.

    :param entity: The entity instance to apply defaults to.
    :param default_names: The field names for which defaults should be applied.
    :return: None.
    """
    defaults = getattr(type(entity), '__deev_defaults__', None)
    if defaults is None or not default_names:
        return
    for name, factory in defaults:
        if name in default_names:
            object.__setattr__(entity, name, factory())


def __default_factories(entity_spec: EntitySpec) -> tuple[tuple[str, Callable[[], Any]], ...]:
    """
    Precompute per-field default factories for fast entity construction.

    Mirrors the default application performed by the ``__init__`` generated
    by :func:`entity`: a non-``None`` callable default is invoked per
    instance, any other default (including ``None``) is stored as-is.

    :param entity_spec: The entity spec whose fields carry defaults.
    :return: Tuples of (field name, zero-argument factory), in field order.
    """
    factories: list[tuple[str, Callable[[], Any]]] = []
    for name, field_spec in entity_spec.fields.items():
        if not hasattr(field_spec, 'default'):
            continue
        default = field_spec.default
        if default is not None and callable(default):
            factories.append((name, cast(Callable[[], Any], default)))
        else:
            factories.append((name, __value_factory(default)))
    return tuple(factories)


def __value_factory(value: Any) -> Callable[[], Any]:
    def factory() -> Any:
        return value
    return factory


def field(
    *,
    autoincrement: bool | None = None,
    cascade_delete: bool | None = None,
    default: Callable[..., Any] | Any | None = __NOTSET__,
    foreign_key: tuple[type, str] | None = None,
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
    :param cascade_delete: When ``True`` and ``foreign_key`` is set, DDL generators emit
        ``ON DELETE CASCADE`` for the foreign key so that deleting a referenced row also
        deletes this row. Default ``None`` (no cascade; cascading must be explicit).
    :param default: Default value or zero-argument callable. Uses sentinel to distinguish "not set" from ``None``.
    :param foreign_key: Foreign-key target as a ``(target_entity_type, target_field_name)``
        tuple, e.g. ``foreign_key=(Parent, 'id')``. Consumed by DDL generators for DBMSes
        that support foreign keys. Default ``None``.
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
    if foreign_key is not None:
        if not (isinstance(foreign_key, tuple) and len(foreign_key) == 2):
            raise ValueError('foreign_key must be a tuple of (target_entity_type, target_field_name).')
        target_type, target_field = foreign_key
        if not isinstance(target_type, type):
            raise ValueError(f'foreign_key target must be an entity type, not {target_type!r}.')
        if not isinstance(target_field, str):
            raise ValueError(f'foreign_key target field must be a string, not {target_field!r}.')
    if isinstance(index, str):
        index = IndexOptions(name=index, direction=IndexOrder.ASCENDING, rank=0)
    field_spec = EntityFieldSpec(
        autoincrement=autoincrement,
        cascade_delete=cascade_delete,
        foreign_key=foreign_key,
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

    **Provider-specific options**

    The following options are consumed by specific database providers and affect DDL generation.
    Options not recognized by the active provider are silently stored in :attr:`EntitySpec.extra_args`
    and have no effect unless the relevant provider implementation reads them.

    **ClickHouse**

    ===========   ========================================================================
    Key           Value
    ===========   ========================================================================
    ``engine``    A valid ClickHouse table engine specification string (e.g. ``'MergeTree'``,
                  ``'ReplacingMergeTree'``, or ``'ReplacingMergeTree()'``). When provided,
                  this is used as the table ``ENGINE`` clause in generated DDL instead of
                  the database-level engine derived from ``system.databases``.
    ===========   ========================================================================
    """
    if cls is None:
        def __entity(_cls: Type[T]) -> Type[T]:
            return entity(_cls, table_name=table_name, no_pluralization=no_pluralization, defer_init=defer_init, snake_case=snake_case, **kwargs)  # type: ignore[bad-return]
        return __entity  # type: ignore[return-value]
    else:
        L_init = None if not hasattr(cls, '__init__') else cast(Callable[..., Any], cls.__init__)
        entity_spec = define_entity_spec(cls, table_name=table_name, no_pluralization=no_pluralization, snake_case=snake_case, **kwargs)

        # NOTE: precomputed once per class so the per-read path below avoids a dict
        #       scan; string hashes are already cached on the spec's field names.
        field_names = frozenset(entity_spec.fields)

        def hide_fieldspec(self: Any, name: str) -> Any:
            v = object.__getattribute__(self, name)
            if self is not None:
                # NOTE: value-first ordering keeps the common case (a plain value)
                #       to two identity checks plus one isinstance.
                if v is None or v is NoneType:
                    # NOTE: unless explicitly spec'd nullable, hide None/NoneType assignments
                    if name not in field_names or entity_spec.fields[name].nullable is not True:
                        raise AttributeError(name)
                elif isinstance(v, EntityFieldSpec):
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

        if (L_init is None or L_init is object.__init__) and getattr(cls, '__new__', object.__new__) is object.__new__:
            # no custom __init__/__new__ to run, so defaults can be applied without the generated __init__
            setattr(cls, '__deev_defaults__', __default_factories(entity_spec))
        setattr(cls, '__init__', init)
        return cls


__all__ = [
    'define_entity_spec',
    'entity',
    'field',
    'get_entity_spec',
    'pluralize',
]
