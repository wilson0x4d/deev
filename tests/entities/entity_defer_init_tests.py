# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from deev import entity, field
from punit import fact, setup, teardown


# --- Module-scoped fixture ---

_seen_defer_init_mixin_init: list[int]


@setup
def module_setup() -> None:
    global _seen_defer_init_mixin_init
    _seen_defer_init_mixin_init = []


@teardown
def module_teardown() -> None:
    global _seen_defer_init_mixin_init
    _seen_defer_init_mixin_init = []


# --- Helper mixins and entity classes ---

class _MixinCallsSuperInit:
    """Mixin that logs when __init__ runs."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        global _seen_defer_init_mixin_init
        _seen_defer_init_mixin_init.append(1)


class _MixinBackingStore:
    """Mixin that sets up a backing dict in __init__ before child field defaults touch __setattr__."""

    _store: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._store = {}
        if super().__init__ is not object.__init__:
            super().__init__(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            self._store[name] = value

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._store:
            return self._store[name]
        raise AttributeError(name)


@dataclass
class _TestItem:
    name: str
    count: int


class _MixinWithDataclass:
    """Mixin that combines with a dataclass-style init pattern."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._prepared = True


@fact
def defer_init_false_applies_defaults_before_base_init() -> None:
    """Without defer_init, field defaults are applied before the base __init__ runs."""
    global _seen_defer_init_mixin_init
    _seen_defer_init_mixin_init = []

    @entity
    class PreInitEntity(_MixinCallsSuperInit):
        x: int = field(default=42)

    instance = PreInitEntity()  # type: ignore[call-arg]
    assert instance.x == 42
    assert len(_seen_defer_init_mixin_init) == 1  # base __init__ ran after defaults


@fact
def defer_init_true_applies_defaults_after_base_init() -> None:
    """With defer_init=True, base __init__ runs before field defaults are applied."""
    global _seen_defer_init_mixin_init
    _seen_defer_init_mixin_init = []

    @entity(defer_init=True)
    class PostInitEntity(_MixinCallsSuperInit):
        x: int = field(default=42)

    instance = PostInitEntity()  # type: ignore[call-arg]
    assert instance.x == 42
    assert len(_seen_defer_init_mixin_init) == 1  # base __init__ ran before defaults


@fact
def defer_init_true_with_backing_store_mixin() -> None:
    """defer_init=True allows mixin with __setattr__ redirecting to backing dict."""
    @entity(defer_init=True)
    class StoreEntity(_MixinBackingStore):
        name: str = field(default='default_name')
        value: int = field(default=0)

    instance = StoreEntity()  # type: ignore[call-arg]
    assert instance.name == 'default_name'
    assert instance.value == 0
    assert hasattr(instance, '_store')
    assert 'name' in instance._store
    assert 'value' in instance._store


@fact
def defer_init_false_with_backing_store_fails() -> None:
    """defer_init=False with a backing store mixin fails because _store doesn't exist when defaults are applied."""
    @entity
    class StoreEntityNoDefer(_MixinBackingStore):
        name: str = field(default='default_name')
        value: int = field(default=0)

    try:
        StoreEntityNoDefer()  # type: ignore[call-arg]
        assert False, 'expected AttributeError because _store not yet initialized'
    except AttributeError:
        pass


@fact
def defer_init_true_kwargs_override_defaults() -> None:
    """kwargs passed to __init__ should override field defaults regardless of defer_init."""
    @entity(defer_init=True)
    class KwargOverride:
        name: str = field(default='supplied_value')

    instance = KwargOverride(name='overridden')  # type: ignore[call-arg]
    assert instance.name == 'overridden'


@fact
def defer_init_false_kwargs_override_defaults() -> None:
    """kwargs override defaults in the original (defer_init=False) behavior too."""
    @entity
    class KwargOverrideNoDefer:
        name: str = field(default='original')

    instance = KwargOverrideNoDefer(name='changed')  # type: ignore[call-arg]
    assert instance.name == 'changed'


@fact
def defer_init_true_callable_default() -> None:
    """Callable defaults work correctly with defer_init=True."""
    call_count = 0

    def gen_id() -> str:
        nonlocal call_count
        call_count += 1
        return f'id_{call_count}'

    @entity(defer_init=True)
    class CallableDefault:
        uid: str = field(default=gen_id)

    instance = CallableDefault()  # type: ignore[call-arg]
    assert instance.uid == 'id_1'


@fact
def defer_init_false_callable_default() -> None:
    """Callable defaults work correctly with defer_init=False."""
    call_count = 0

    def gen_id() -> str:
        nonlocal call_count
        call_count += 1
        return f'gen_{call_count}'

    @entity
    class CallableDefaultNoDefer:
        uid: str = field(default=gen_id)

    instance1 = CallableDefaultNoDefer()  # type: ignore[call-arg]
    instance2 = CallableDefaultNoDefer()  # type: ignore[call-arg]
    assert instance1.uid == 'gen_1'
    assert instance2.uid == 'gen_2'


@fact
def defer_init_true_with_datetime_default() -> None:
    """Timestamp-style callable defaults work with defer_init=True."""
    @entity(defer_init=True)
    class TimestampEntity:
        created: datetime = field(default=lambda: datetime.now(timezone.utc))

    instance = TimestampEntity()  # type: ignore[call-arg]
    assert instance.created is not None
    assert instance.created.tzinfo is not None


@fact
def defer_init_true_no_custom_init() -> None:
    """defer_init=True with no custom __init__ still applies defaults (calls object.__init__)."""
    @entity(defer_init=True)
    class PlainEntity:
        name: str = field(default='hello')
        count: int = field(default=100)

    instance = PlainEntity()  # type: ignore[call-arg]
    assert instance.name == 'hello'
    assert instance.count == 100


@fact
def defer_init_false_no_custom_init() -> None:
    """defer_init=False with no custom __init__ still applies defaults (original behavior)."""
    @entity
    class PlainEntityNoDefer:
        name: str = field(default='hello')
        count: int = field(default=100)

    instance = PlainEntityNoDefer()  # type: ignore[call-arg]
    assert instance.name == 'hello'
    assert instance.count == 100


@fact
def defer_init_true_mixin_sets_flags() -> None:
    """Mixins that set internal flags in __init__ work when they run before field defaults."""
    @entity(defer_init=True)
    class FlagEntity(_MixinWithDataclass):
        ready: bool
        label: str = field(default='ready_label')

    instance = FlagEntity(ready=True)  # type: ignore[call-arg]
    assert instance._prepared is True
    assert instance.label == 'ready_label'


@fact
def defer_init_true_multiple_fields() -> None:
    """Multiple field defaults are applied correctly with defer_init=True."""
    @entity(defer_init=True)
    class MultiFieldEntity:
        a: int = field(default=1)
        b: int = field(default=2)
        c: int = field(default=3)
        d: Optional[str] = field(default='ok')

    instance = MultiFieldEntity()  # type: ignore[call-arg]
    assert instance.a == 1
    assert instance.b == 2
    assert instance.c == 3
    assert instance.d == 'ok'


@fact
def defer_init_parameterized_decorator() -> None:
    """@entity(defer_init=True) works as a parameterized decorator form."""
    @entity(defer_init=True)
    class ParameterizedEntity:
        x: str = field(default='from_parameterized')

    instance = ParameterizedEntity()  # type: ignore[call-arg]
    assert instance.x == 'from_parameterized'


@fact
def defer_init_true_with_init_parameter() -> None:
    """defer_init=True with custom __init__ in entity class (init parameter not field spec)."""
    global _seen_defer_init_mixin_init
    _seen_defer_init_mixin_init = []

    @entity(defer_init=True)
    class CustomInitDefer:
        x: int = field(default=7)

        def __init__(self, y: int = 0, *args: Any, **kwargs: Any) -> None:
            self.y = y
            if super().__init__ is not object.__init__:
                super().__init__(*args, **kwargs)

    instance = CustomInitDefer(y=42)  # type: ignore[call-arg]
    assert instance.x == 7
    assert instance.y == 42


@fact
def defer_init_false_with_init_parameter() -> None:
    """defer_init=False with custom __init__ in entity class."""
    global _seen_defer_init_mixin_init
    _seen_defer_init_mixin_init = []

    @entity
    class CustomInitNoDefer:
        x: int = field(default=7)

        def __init__(self, y: int = 0, *args: Any, **kwargs: Any) -> None:
            self.y = y
            if super().__init__ is not object.__init__:
                super().__init__(*args, **kwargs)

    instance = CustomInitNoDefer(y=42)  # type: ignore[call-arg]
    assert instance.x == 7
    assert instance.y == 42
