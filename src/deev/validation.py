# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from decimal import Decimal
from typing import Optional, final


@final
class ValidationError(Exception):
    """Exception raised when a value fails validation for a specific field."""

    def __init__(self, field_name: str, reason: str) -> None:
        self.field_name = field_name
        self.reason = reason
        super().__init__(f'Validation error on {field_name}: {reason}')

    def __repr__(self) -> str:
        return (f'{self.__class__.__name__}'
                f'(field_name={self.field_name!r}, reason={self.reason!r})')

    def __str__(self) -> str:
        return f'Validation error on {self.field_name}: {self.reason}'


def validate(entity: object, attrs: Optional[list[str]] = None) -> list[ValidationError] | None:
    """
    Runs validations for the target entity.

    :param entity: The entity to validate.
    :param attrs: A list of attributes to be validated, otherwise validates all.
    :return: A list containing validation errors, or None if no validation errors.
    """
    from .entities import get_entity_spec
    validation_errors = list[ValidationError]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for field_name, field_spec in entity_spec.fields.items():
        if attrs is not None and field_name not in attrs:
            continue
        attr_value = getattr(entity, field_name, None)
        if attr_value is not None or field_spec.nullable is True:
            if hasattr(field_spec, 'validator') and field_spec.validator is not None:
                try:
                    validation_error = field_spec.validator(attr_value)
                    if validation_error is not None:
                        validation_errors.append(validation_error)
                except ValidationError as ve:
                    validation_errors.append(ve)
            if hasattr(field_spec, 'min') and field_spec.min is not None:
                if isinstance(attr_value, str):
                    if len(attr_value) < field_spec.min:
                        validation_errors.append(ValidationError(
                            field_name,
                            f'LEN < {field_spec.min}'
                        ))
                elif isinstance(attr_value, (int, float, Decimal)):
                    if attr_value < field_spec.min:
                        validation_errors.append(ValidationError(
                            field_name,
                            f'VAL < {field_spec.min}'
                        ))
            if hasattr(field_spec, 'max') and field_spec.max is not None:
                if isinstance(attr_value, str):
                    if len(attr_value) > field_spec.max:
                        validation_errors.append(ValidationError(
                            field_name,
                            f'LEN > {field_spec.max}'
                        ))
                elif isinstance(attr_value, (int, float, Decimal)):
                    if attr_value > field_spec.max:
                        validation_errors.append(ValidationError(
                            field_name,
                            f'VAL > {field_spec.max}'
                        ))
        elif hasattr(field_spec, 'nullable') and field_spec.nullable is not None:
            if field_spec.nullable is False and attr_value is None:
                validation_errors.append(ValidationError(
                    field_name,
                    'Cannot be NULL.'
                ))
    return None if len(validation_errors) == 0 else validation_errors


__all__ = [
    'ValidationError',
    'validate'
]
