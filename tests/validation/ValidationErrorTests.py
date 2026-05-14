# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.validation import ValidationError
from punit import fact



@fact
def basic_verification() -> None:
    try:
        raise ValidationError(field_name='foo', reason='bar')
    except ValidationError as verr:
        assert verr.field_name == 'foo', 'field name not set.'
        assert verr.reason == 'bar', 'reason not set.'
        assert str(verr) == "Validation error on foo: bar", 'str result incorrect.'
        assert verr.__repr__() == "ValidationError(field_name='foo', reason='bar')", 'repr result incorrect.'


