# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

"""
Behavioral pinning tests for the ``hide_fieldspec`` ``__getattribute__``
override installed by the ``@entity`` decorator (src/deev/entities/utils.py):

- unassigned fields carrying an ``EntityFieldSpec`` class attribute read as missing
- ``None``/``NoneType`` assignments to non-nullable fields read as missing
- ``None``/``NoneType`` on nullable fields reads back
- incidental: ``None``/``NoneType`` (or an ``EntityFieldSpec``) assigned to a
  *non-field* attribute also raises ``AttributeError`` (read as missing)
- class-level access bypasses the override entirely
- an ``AttributeError`` raised by the override still permits a ``__getattr__``
  fallback (see the defer-init backing-store mixin tests)
"""

from types import NoneType

from deev import entity, field
from deev.entities import EntityFieldSpec
from punit import fact


@entity
class HideFixture:
    spec_pk: int = field(primary_key=True)  # spec, no default: class attr is an EntityFieldSpec
    bare_field: str  # annotation only: no class attribute at all
    nullable: str | None = field(nullable=True)  # nullable, no default
    non_nullable: str = field(nullable=False)  # non-nullable, explicit
    nullable_default_none: str | None = field(default=None)  # nullable, default None
    non_nullable_default: int = field(default=42)  # non-nullable, default value
    # non-field attributes (no type hint: not part of the entity spec)
    typed_none: int | None = None
    untyped_none = None  # type: ignore
    untyped_value = 'hello'  # type: ignore


@fact
def unassigned_field_spec_reads_as_missing() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    assert hasattr(h, 'spec_pk') is False
    try:
        h.spec_pk  # type: ignore[unreachable]
    except AttributeError as e:
        assert e.args == ('spec_pk',)
    else:
        raise AssertionError('expected AttributeError for unassigned field spec.')


@fact
def assigned_field_spec_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    h.spec_pk = 1
    assert h.spec_pk == 1


@fact
def unassigned_bare_field_reads_as_missing() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    assert hasattr(h, 'bare_field') is False
    try:
        h.bare_field  # type: ignore[unreachable]
    except AttributeError:
        pass
    else:
        raise AssertionError('expected AttributeError for unassigned bare field.')


@fact
def nullable_field_none_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    h.nullable = None
    assert h.nullable is None


@fact
def nullable_field_none_type_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    object.__setattr__(h, 'nullable', NoneType)
    assert h.nullable is NoneType


@fact
def nullable_field_value_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    h.nullable = 'x'
    assert h.nullable == 'x'


@fact
def non_nullable_none_reads_as_missing() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    object.__setattr__(h, 'non_nullable', None)
    assert hasattr(h, 'non_nullable') is False
    try:
        h.non_nullable  # type: ignore[unreachable]
    except AttributeError as e:
        assert e.args == ('non_nullable',)
    else:
        raise AssertionError('expected AttributeError for None on non-nullable field.')


@fact
def non_nullable_none_type_reads_as_missing() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    object.__setattr__(h, 'non_nullable', NoneType)
    assert hasattr(h, 'non_nullable') is False
    try:
        h.non_nullable  # type: ignore[unreachable]
    except AttributeError:
        pass
    else:
        raise AssertionError('expected AttributeError for NoneType on non-nullable field.')


@fact
def nullable_default_none_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    assert h.nullable_default_none is None


@fact
def non_nullable_default_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    assert h.non_nullable_default == 42


@fact
def non_field_none_class_attr_reads_as_missing() -> None:
    # NOTE: incidental pre-optimization behavior: a None-valued attribute that is
    #       not part of the entity spec also raises AttributeError (type is pinned,
    #       the message is not).
    h = HideFixture()  # type: ignore[call-arg]
    assert hasattr(h, 'untyped_none') is False
    try:
        h.untyped_none  # type: ignore[unreachable]
    except AttributeError:
        pass
    else:
        raise AssertionError('expected AttributeError for None-valued non-field attribute.')


@fact
def non_field_none_instance_attr_reads_as_missing() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    h.inst_none = None  # type: ignore[attr-defined]
    assert hasattr(h, 'inst_none') is False  # type: ignore[arg-type]
    try:
        h.inst_none  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:
        raise AssertionError('expected AttributeError for None-valued non-field instance attribute.')


@fact
def non_field_spec_value_reads_as_missing() -> None:
    # NOTE: incidental pre-optimization behavior: assigning an EntityFieldSpec to a
    #       non-field attribute hides it.
    h = HideFixture()  # type: ignore[call-arg]
    h.spec_attr = field(nullable=True)  # type: ignore[attr-defined]
    assert hasattr(h, 'spec_attr') is False  # type: ignore[arg-type]
    try:
        h.spec_attr  # type: ignore[attr-defined]
    except AttributeError as e:
        assert e.args == ('spec_attr',)
    else:
        raise AssertionError('expected AttributeError for EntityFieldSpec-valued non-field attribute.')


@fact
def non_field_value_reads_back() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    assert h.untyped_value == 'hello'
    h.inst_val = 7  # type: ignore[attr-defined]
    assert h.inst_val == 7  # type: ignore[attr-defined]


@fact
def missing_attr_still_missing() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    assert hasattr(h, 'does_not_exist') is False  # type: ignore[arg-type]


@fact
def class_level_access_bypasses_override() -> None:
    # class-level reads go through the metaclass, not the instance __getattribute__
    assert isinstance(HideFixture.spec_pk, EntityFieldSpec) is True
    assert HideFixture.untyped_none is None
    assert HideFixture.untyped_value == 'hello'


@fact
def instance_dict_unaffected() -> None:
    h = HideFixture()  # type: ignore[call-arg]
    h.non_nullable_default = 99
    assert h.__dict__['non_nullable_default'] == 99
    assert 'spec_pk' not in h.__dict__


@fact
def attribute_error_permits_getattr_fallback() -> None:
    # a hidden attribute must surface as AttributeError so a __getattr__ fallback
    # (e.g. the defer-init backing-store mixin) is still consulted.
    class BackingStore:
        _store: dict[str, object]

        def __init__(self) -> None:
            self._store = {'value': 'from-fallback'}

        def __getattr__(self, name: str) -> object:
            if name in self._store:
                return self._store[name]
            raise AttributeError(name)

    @entity
    class FallbackEntity(BackingStore):
        value: str = field(nullable=True)

    instance = FallbackEntity()  # type: ignore[call-arg]
    # 'value' has no instance dict entry (no default), so the class-level spec is
    # hidden by the override and the __getattr__ fallback must answer the read.
    assert instance.value == 'from-fallback'
