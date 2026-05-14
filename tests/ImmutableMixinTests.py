# SPDX-FileCopyrightText: © 2025 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev._ImmutableMixin import _ImmutableMixin
from punit import fact


@fact
def when_frozen_then_setattr_raises() -> None:
    class FreezableOne(_ImmutableMixin):
        a: int
    foo = FreezableOne()
    foo.a = 1
    assert foo.a == 1
    foo.__freeze__()
    try:
        foo.a = 2
    except AttributeError:
        pass
    else:
        raise AssertionError(f'should not be able to setattr a frozen object.')


@fact
def when_frozen_then_delattr_raises() -> None:
    class FreezableTwo(_ImmutableMixin):
        a: int
    foo = FreezableTwo()
    foo.a = 1
    setattr(foo, 'b', 2)
    assert foo.a == 1
    assert foo.b == 2  # type: ignore[attr-defined]
    del foo.a
    assert hasattr(foo, 'a') is False
    foo.__freeze__()
    try:
        del foo.b  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:
        raise AssertionError(f'should not be able to delattr a frozen object.')
