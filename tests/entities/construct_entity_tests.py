# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import apply_defaults_for, construct_entity, entity, field
from punit import fact


@fact
def construct_entity_applies_value_defaults() -> None:
    @entity
    class Widget:
        id: int = field(primary_key=True, default=7)
        name: str = 'anon'
        count: int = 0

    w = construct_entity(Widget)
    assert w.id == 7, f'expected id 7, got {w.id}'
    assert w.name == 'anon', f'expected name "anon", got {w.name}'
    assert w.count == 0, f'expected count 0, got {w.count}'


@fact
def construct_entity_invokes_callable_defaults_per_instance() -> None:
    @entity
    class Thing:
        id: int = field(primary_key=True, default=0)
        stamps: list[int] = field(default=lambda: [])

    a = construct_entity(Thing)
    b = construct_entity(Thing)
    assert a.stamps == [], f'expected empty list, got {a.stamps}'
    assert b.stamps == [], f'expected empty list, got {b.stamps}'
    assert a.stamps is not b.stamps, 'expected a fresh list per instance'


@fact
def construct_entity_empty_names_applies_no_defaults() -> None:
    @entity
    class Widget:
        id: int = field(primary_key=True, default=7)

    w = construct_entity(Widget, ())
    assert 'id' not in vars(w), f'expected no defaults applied, got {vars(w)}'


@fact
def construct_entity_selective_defaults() -> None:
    @entity
    class Widget:
        id: int = field(primary_key=True, default=7)
        name: str = 'anon'

    w = construct_entity(Widget, ['name'])
    assert w.name == 'anon', f'expected name "anon", got {w.name}'
    assert 'id' not in vars(w), f'expected id absent, got {vars(w)}'


@fact
def apply_defaults_for_applies_enumerated_defaults() -> None:
    @entity
    class Widget:
        id: int = field(primary_key=True, default=7)
        name: str = 'anon'

    w = construct_entity(Widget, ())
    apply_defaults_for(w, ['id', 'name'])
    assert w.id == 7, f'expected id 7, got {w.id}'
    assert w.name == 'anon', f'expected name "anon", got {w.name}'


@fact
def apply_defaults_for_leaves_unlisted_fields() -> None:
    @entity
    class Widget:
        id: int = field(primary_key=True, default=7)
        name: str = 'anon'

    w = construct_entity(Widget, ())
    w.name = 'filled'
    apply_defaults_for(w, ['id'])
    assert w.id == 7, f'expected id 7, got {w.id}'
    assert w.name == 'filled', f'expected name "filled" to be left untouched, got {w.name}'


@fact
def apply_defaults_for_ignores_unknown_names() -> None:
    @entity
    class Widget:
        id: int = field(primary_key=True, default=7)

    w = construct_entity(Widget, ())
    apply_defaults_for(w, ['id', 'does_not_exist'])
    assert w.id == 7, f'expected id 7, got {w.id}'
    assert 'does_not_exist' not in vars(w), f'unexpected attribute set: {vars(w)}'


@fact
def construct_entity_falls_back_for_custom_init() -> None:
    @entity
    class Custom:
        value: int = field(default=5)

        def __init__(self, value: int = 99) -> None:
            self.value = value

    w = construct_entity(Custom)
    assert w.value == 99, f'expected the custom __init__ to run (99), got {w.value}'


@fact
def construct_entity_matches_constructor_defaults() -> None:
    @entity
    class Parity:
        id: int = field(primary_key=True, default=3)
        name: str = 'x'
        items: list[int] = field(default=lambda: [])

        def __init__(self) -> None:
            self.fresh = id(self)

    a = construct_entity(Parity)
    b = Parity()
    assert a.id == b.id == 3, f'expected id 3 on both, got {a.id} and {b.id}'
    assert a.name == b.name == 'x', f'expected name "x" on both, got {a.name} and {b.name}'
    assert a.items == b.items == [], f'expected empty lists, got {a.items} and {b.items}'
