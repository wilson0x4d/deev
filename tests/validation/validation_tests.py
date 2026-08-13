# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from decimal import Decimal
from deev import entity, field
from deev.validation import ValidationError, validate
from punit import fact, inlinedata, theory
from typing import Any


@fact
def validation_skips_unspecified_attrs() -> None:
    @entity
    class VSUA:
        a: int = field(min=3, max=5)
        b: int = field(min=-5, max=-3)
    obj = VSUA(a=2, b=-4)
    assert validate(obj, ['b']) is None
    assert validate(obj, ['a']) is not None


@theory
@inlinedata(3, True)
@inlinedata(3.0, True)
@inlinedata(Decimal(3), True)
@inlinedata("123", True)
@inlinedata(2, False)
@inlinedata(2.0, False)
@inlinedata(Decimal(2), False)
@inlinedata("12", False)
@inlinedata(6, False)
@inlinedata(6.0, False)
@inlinedata(Decimal(6), False)
@inlinedata("123456", False)
def validation_min_max(value: str | int | float | Decimal, expect_success: bool) -> None:
    @entity
    class VMM1:
        s: str = field(min=3, max=5, default="1234")
        i: int = field(min=3, max=5, default=4)
        f: float = field(min=3.0, max=5.0, default=4.0)
        d: Decimal = field(min=Decimal(3), max=Decimal(5), default=Decimal(4))
    obj: VMM1
    if isinstance(value, str):
        obj = VMM1(s=value)
    elif isinstance(value, int):
        obj = VMM1(i=value)
    elif isinstance(value, float):
        obj = VMM1(f=value)
    elif isinstance(value, Decimal):
        obj = VMM1(d=value)
    assert (validate(obj) is None) == expect_success


@theory
@inlinedata(3, True)
@inlinedata(3.0, True)
@inlinedata(Decimal(3), True)
@inlinedata("123", True)
@inlinedata(2, False)
@inlinedata(2.0, False)
@inlinedata(Decimal(2), False)
@inlinedata("12", False)
@inlinedata(6, False)
@inlinedata(6.0, False)
@inlinedata(Decimal(6), False)
@inlinedata("123456", False)
def validation_min_max_when_optional(value: str | int | float | Decimal, expect_success: bool) -> None:
    @entity
    class VMM1:
        s: str | None = field(min=3, max=5, default=None)
        i: int | None = field(min=3, max=5, default=None)
        f: float | None = field(min=3.0, max=5.0, default=None)
        d: Decimal | None = field(min=Decimal(3), max=Decimal(5), default=None)
    obj: VMM1
    if isinstance(value, str):
        obj = VMM1(s=value)
    elif isinstance(value, int):
        obj = VMM1(i=value)
    elif isinstance(value, float):
        obj = VMM1(f=value)
    elif isinstance(value, Decimal):
        obj = VMM1(d=value)
    assert (validate(obj) is None) == expect_success


@fact
def explicit_non_nullable_raises_when_null() -> None:
    @entity
    class ENNRWN:
        s: str | None = field(min=3, max=5, default=None, nullable=False)
    obj = ENNRWN(s=None)
    assert validate(obj) is not None


@fact
def explicit_nullable_does_not_raise_when_null() -> None:
    @entity
    class ENDNRWN:
        s: str | None = field(min=3, max=5, default=None, nullable=True)
    obj = ENDNRWN(s=None)
    assert validate(obj) is None


@fact
def validator_callback_bvt() -> None:
    def invalid_when_null(v: Any) -> ValidationError | None:
        if v is None:
            return ValidationError('invalid_when_null', 'invalid_when_null')
        return None

    def invalid_when_non_null(v: Any) -> ValidationError | None:
        if v is not None:
            return ValidationError('invalid_when_non_null', 'invalid_when_non_null')
        return None

    @entity
    class VCBVT:
        a: str | None = field(default=None, nullable=True, validator=invalid_when_null)
        b: str | None = field(default=None, nullable=True, validator=invalid_when_non_null)
    assert validate(VCBVT(a="123")) is None
    assert len(validate(VCBVT(a="123", b="bob"))) == 1  # type: ignore[arg-type]
    assert len(validate(VCBVT(a=None, b="bob"))) == 2  # type: ignore[arg-type]
    assert len(validate(VCBVT())) == 1  # type: ignore[arg-type]


@fact
def validator_callback_can_raise() -> None:
    def invalid_when_null(v: Any) -> ValidationError | None:
        if v is None:
            raise ValidationError('invalid_when_null', 'invalid_when_null')
        return None

    def invalid_when_non_null(v: Any) -> ValidationError | None:
        if v is not None:
            raise ValidationError('invalid_when_non_null', 'invalid_when_non_null')
        return None

    @entity
    class VCBVT:
        a: str | None = field(default=None, nullable=True, validator=invalid_when_null)
        b: str | None = field(default=None, nullable=True, validator=invalid_when_non_null)
    assert validate(VCBVT(a="123")) is None
    assert len(validate(VCBVT(a="123", b="bob"))) == 1  # type: ignore[arg-type]
    assert len(validate(VCBVT(a=None, b="bob"))) == 2  # type: ignore[arg-type]
    assert len(validate(VCBVT())) == 1  # type: ignore[arg-type]
