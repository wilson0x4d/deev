Validation
==========

Entity fields carry declarative validation rules in their specs: ``min``, ``max``, ``nullable``, and an optional custom ``validator``. Use :func:`~deev.validation.validate` to run them on demand:

.. code-block:: python

    from deev import entity, field
    from deev.validation import validate, ValidationError


    def validate_email(value):
        if value is None:
            return None
        if '@' not in value:
            return ValidationError('email', 'must be a valid email address')
        return None


    @entity
    class User:
        id: int = field(autoincrement=True, primary_key=True)
        name: str = field(min=1, max=256)
        email: str | None = field(default=None, validator=validate_email)
        score: int | None = field(default=None, min=0, max=100)


    user = User(name='', email='not-an-email', score=150)
    errors = validate(user)
    if errors:
        for error in errors:
            print(error.field_name, '-', error.reason)

    # name  - LEN < 1
    # email - must be a valid email address
    # score - VAL > 100


How Validation Works
--------------------

* ``validate(entity, attrs=None)`` returns a ``list[ValidationError]`` containing every failure, or ``None`` when the entity is valid. Pass ``attrs`` to restrict validation to specific fields.
* ``min`` / ``max`` — for ``str`` fields these bound string *length*; for ``int``/``float``/``Decimal`` fields they bound the numeric *value*.
* ``nullable`` — a field explicitly marked ``nullable=False`` fails validation when its value is ``None``. (``Optional[...]`` annotations imply ``nullable=True``.)
* ``validator`` — a callable invoked with the field value. Return ``None`` to pass, return (or raise) a :class:`~deev.validation.ValidationError` to fail.
* ``None`` values are skipped for ``min``/``max``/``validator`` checks unless the field is explicitly non-nullable, so partially-filled entities validate sensibly.

:class:`~deev.validation.ValidationError` exposes ``field_name`` and ``reason`` attributes.
