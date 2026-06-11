# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from deev import DbError, entity, field
from deev.entities import EntityFieldSpec, EntitySpec, define_entity_spec, get_entity_spec
from deev.validation import ValidationError, validate
from punit import fact
from typing import Any, Optional
from uuid import UUID, uuid4


@entity
class MyEntity:
    implied_nullable_with_non_nullable_spec: Optional[int] = field(nullable=False)
    implied_nullable: Optional[int]
    description: Optional[str] = field(
        default=None,
        unique=True,
        dbtype='VARCHAR(20)',
        nullable=False
    )
    id: UUID = field(
        default=uuid4,
        primary_key=True
    )
    title: Optional[str] = field(
        default=None,
        validator=lambda x: None if x is None or (len(x) > 0 and len(x) <= 30) else ValidationError(
            'title', 'failed validation checks.'
        )
    )
    sku: str = field(
        default='12345',
        index='ix_myentity_sku',
        dbtype='CHAR(5)',
        min=5,
        max=5,
    )
    non_nullable_with_default: int = 234
    implied_nullable_with_default: Optional[int] = 345


@fact
def field_default_supports_callback() -> None:
    e = MyEntity()  # type: ignore[call-arg]
    assert e.id is not None


@fact
def field_default_supports_value() -> None:
    e = MyEntity()  # type: ignore[call-arg]
    assert e.sku == '12345'


@fact
def field_default_supports_override() -> None:
    id = uuid4()
    e = MyEntity(  # type: ignore[call-arg]
        id=id
    )
    assert e.id == id


@fact
def field_validator_executes() -> None:
    e = MyEntity(  # type: ignore[call-arg]
        title=''
    )
    validate(e)


@fact
def entity_spec_immutability_check() -> None:
    spec = EntitySpec(
        attrs={},
        entity_type=MyEntity,
        fields={},
        has_autoincrement=False,
        primary_key=('id',),
        table_name='foo'
    )
    spec.table_name = 'bar'
    spec.__freeze__()
    try:
        spec.table_name = 'baz'
    except AttributeError:
        pass
    else:
        assert spec.table_name == 'bar', 'instance should have immutability.'


@fact
def entityfield_spec_immutability_check() -> None:
    spec = EntityFieldSpec(
        default='bar'
    )
    spec.default = 'baz'
    spec.__freeze__()
    try:
        spec.default = 'foo'
    except AttributeError:
        pass
    else:
        assert spec.default == 'baz', 'instance should have immutability.'


@fact
def entity_table_name_overridable() -> None:
    table_name = uuid4().hex

    @entity(table_name=table_name)
    class ETNO:
        x: int

    spec = get_entity_spec(ETNO)
    assert spec.table_name == table_name


@fact
def entity_supports_primary_key_simple() -> None:
    @entity
    class ESPKS:
        id: int = field(
            primary_key=True
        )

    spec = get_entity_spec(ESPKS)
    assert spec.primary_key is not None, 'primary_key was not defined.'
    assert len(spec.primary_key) == 1, 'primary_key incorrect size.'
    assert spec.primary_key[0] == 'id', 'primary_key malformed.'


@fact
def entity_supports_primary_key_complex() -> None:
    @entity
    class ESPKC:
        nonpk: str
        pk1: int = field(primary_key=True)
        pk2: int = field(primary_key=True)
        pk3: int = field(primary_key=True)

    spec = get_entity_spec(ESPKC)
    assert spec.primary_key is not None, 'primary_key was not defined.'
    assert len(spec.primary_key) == 3, 'primary_key incorrect size.'
    assert spec.primary_key[0] == 'pk1', 'primary_key malformed at position 1.'
    assert spec.primary_key[1] == 'pk2', 'primary_key malformed at position 2.'
    assert spec.primary_key[2] == 'pk3', 'primary_key malformed at position 3.'


@fact
def entity_supports_primary_key_with_autoincrement() -> None:
    @entity
    class ESPKWA:
        nonpk: str
        pk1: int = field(primary_key=True, autoincrement=True)
        pk2: int = field(primary_key=True)
        pk3: int = field(primary_key=True)

    spec = get_entity_spec(ESPKWA)
    assert spec.primary_key is not None, 'primary_key was not defined.'
    assert len(spec.primary_key) == 3, 'primary_key incorrect size.'
    assert spec.primary_key[0] == 'pk1', 'primary_key malformed at position 1.'
    assert spec.primary_key[1] == 'pk2', 'primary_key malformed at position 2.'
    assert spec.primary_key[2] == 'pk3', 'primary_key malformed at position 3.'
    assert spec.has_autoincrement is True, 'missing autoincrement.'


@fact
def entity_supports_attribute_only_definition() -> None:
    @entity
    class ESAOD:
        attr3: int
        attr2: int
        attr1: int

    spec = get_entity_spec(ESAOD)
    # specs do not have optional fields, if a PK is not defined the spec for it appears empty
    assert spec.primary_key is not None, 'unexpected undefined primary_key.'
    assert len(spec.primary_key) == 0, 'primary key incorrect size.'
    assert len(spec.attrs) == 3, 'incorrect attribute count.'
    assert 'attr3' in spec.attrs, 'missing expected attr at position 1'
    assert 'attr2' in spec.attrs, 'missing expected attr at position 2'
    assert 'attr1' in spec.attrs, 'missing expected attr at position 3'
    assert spec.has_autoincrement is False, 'unexpected autoincrement flag.'


@fact
def when_invalid_union_then_raises() -> None:
    try:
        @entity
        class WithUnsupportedUnion:
            a: Optional[int | str]  # NOTE: cannot express multiple types
    except DbError:
        pass
    else:
        raise AssertionError('expected error for unsupported union')


@fact
def when_valid_union_then_not_raises() -> None:
    # NOTE: the types used (int, str) are not as relevant as being unionized with None/NoneType
    @entity
    class WithSupportedUnions:
        a: Optional[int]
        b: str | None


@fact
def can_define_adhoc_entity() -> None:
    # NOTE: considered ad-hoc because no @entity decorator
    class AdhocEntityClass:
        a: int
    entity_spec = define_entity_spec(AdhocEntityClass)
    assert entity_spec is not None
    assert 'a' in entity_spec.attrs
    assert entity_spec.attrs.get('a') is int
    # considered ad-hoc because decorator imperatively applied
    adhoc_entity = entity()(AdhocEntityClass)
    adhoc_instance = adhoc_entity()
    assert adhoc_instance is not None
    assert isinstance(adhoc_instance, AdhocEntityClass)


@fact
def entity_can_supply_init() -> None:
    @entity
    class EntityWithInit:
        foo: str
        bar: bool

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.bar = True
            assert kwargs.get('foo', None) == 'bar', 'kwargs not passed through.'
    instance = EntityWithInit(foo='bar')
    assert instance is not None, 'instance not cretable.'
    assert instance.foo == 'bar', 'atribute not settable.'
    assert instance.bar is True, 'init not observable.'


@fact
def undefined_entity_should_return_new_definition() -> None:
    class Foo:
        bar: str
    entity_spec = get_entity_spec(Foo)
    assert entity_spec is not None


@fact
def implied_nullable_when_unassigned_hides_value() -> None:
    obj = MyEntity()  # type: ignore[call-arg]
    assert hasattr(obj, 'implied_nullable') is False


@fact
def implied_nullable_when_assigned_yields_value() -> None:
    obj = MyEntity()  # type: ignore[call-arg]
    obj.implied_nullable = None
    assert obj.implied_nullable is None


@fact
def non_nullable_with_default() -> None:
    obj = MyEntity()  # type: ignore[call-arg]
    assert obj.non_nullable_with_default == 234


@fact
def implied_nullable_with_default() -> None:
    obj = MyEntity()  # type: ignore[call-arg]
    assert obj.implied_nullable_with_default == 345


@fact
def implied_nullable_with_non_nullable_spec() -> None:
    obj = MyEntity()  # type: ignore[call-arg]
    assert hasattr(obj, 'implied_nullable_with_non_nullable_spec') is False


@fact
def pluralization_bvt() -> None:
    from deev.entities import pluralize
    assert pluralize('Widgets') == 'Widgets', 'not respecting already plural.'
    assert pluralize('Tree') == 'Trees', 'not applying default pluralization.'
    assert pluralize('Anatoly') == 'Anatolies', 'not applying consonantal pluralization.'
