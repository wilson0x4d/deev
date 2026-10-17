# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from types import NoneType, UnionType
import inspect
from typing import Any, Callable, Mapping, Union, get_args, get_origin

from .datetime_utils import assume_utc, ensure_utc_aware, get_mssql_datetime_type
from .deev_json_decoder import DeevJsonDecoder, _parse_datetime_iso, _parse_time_iso
from .deev_json_encoder import DeevJsonEncoder, _iso_z, _utc_z, _utc_z_time
from ..entities import get_entity_spec
from uuid import UUID

__json_encoder: type[json.JSONEncoder] = DeevJsonEncoder
__json_decoder: type[json.JSONDecoder] = DeevJsonDecoder
__serializer: Callable[[Any], str] | None = None
__deserializer: Callable[[Any], str] | None = None


def __to_json(obj: Any) -> str:
    return (
        __serializer(obj)
        if __serializer is not None
        else json.dumps(
            obj,
            ensure_ascii=False,
            cls=__json_encoder,
            indent=None,
            separators=(',', ':')
        )
    )


def __from_json(s: str) -> Any:
    return (
        __deserializer(s)
        if __deserializer is not None
        else json.loads(
            s,
            cls=__json_decoder
        )
    )


def __apply_datetime_read_policy(dt: datetime, from_sql: bool, from_mssql: bool, from_bson: bool, from_mysql: bool, from_chsql: bool) -> datetime:
    """
    Apply the provider-specific read policy for datetime values.

    Naive values are always treated as UTC (tagged via ``replace``).
    Timezone-aware values depend on the store: stores that can carry the
    offset (SQLite, MSSQL ``DATETIMEOFFSET``, and the provider-agnostic JSON
    path) return them unchanged; stores that cannot (MySQL, ClickHouse,
    MongoDB, and MSSQL with any other ``DEEV__MSSQL__DATETIME_TYPE``) are
    normalized to UTC (defensively — their drivers return naive values).

    :param dt: The datetime value to normalize.
    :param from_sql: True when the value came from SQLite.
    :param from_mssql: True when the value came from SQL Server.
    :param from_bson: True when the value came from MongoDB.
    :param from_mysql: True when the value came from MySQL.
    :param from_chsql: True when the value came from ClickHouse.
    :return: A timezone-aware datetime.
    :raises ValueError: If more than one provider flag is specified.
    """
    if sum((from_sql, from_mssql, from_bson, from_mysql, from_chsql)) > 1:
        raise ValueError('Only one of `from_sql`, `from_mssql`, `from_bson`, `from_mysql`, `from_chsql` may be specified.')
    if from_mssql and get_mssql_datetime_type() != 'DATETIMEOFFSET':
        return assume_utc(dt)
    if from_mysql or from_chsql or from_bson:
        return assume_utc(dt)
    return ensure_utc_aware(dt)


def configure_serialization(  # pragma: no cover
    *,
    encoder: type[json.JSONEncoder] | None = None,
    decoder: type[json.JSONDecoder] | None = None,
    serializer: Callable[[Any], str] | None = None,
    deserializer: Callable[[str], Any] | None = None
) -> None:
    """
    Configure JSON encoders/decoders used for value serialization.

    Complex types (lists, tuples, dicts, Decimals, UUIDs, etc.) are serialized
    to JSON strings when stored to the database. This function allows customization
    of the serialization behavior.

    :param encoder: Custom JSON encoder class.
    :param decoder: Custom JSON decoder class.
    :param serializer: Custom serializer callable (``obj -> str``). Overrides encoder/decoder.
    :param deserializer: Custom deserializer callable (``str -> obj``). Overrides encoder/decoder.
    :raises RuntimeError: If encoder/decoder are set after a custom serializer/deserializer.

    .. note:: If custom ``serializer``/``deserializer`` are provided, ``encoder``/``decoder`` cannot be used.
    """
    global __json_encoder
    global __json_decoder
    global __serializer
    global __deserializer
    if serializer is not None:
        __serializer = serializer
    if deserializer is not None:
        __deserializer = deserializer
    if encoder is not None:
        if __serializer is not None:
            raise RuntimeError('Attempt to set encoder when the default serializer has been overridden.')
        else:
            __json_encoder = encoder
    if decoder is not None:
        if __deserializer is not None:
            raise RuntimeError('Attempt to set decoder when the default deserializer has been overridden.')
        else:
            __json_decoder = decoder


def deunionize(t: type) -> type:
    """
    Extract the non-None type from a ``Union``/``Optional`` type hint.

    :param t: A type hint (e.g. ``Optional[str]``).
    :return: The non-None type argument, or the type unchanged if not a Union.
    """
    if get_origin(t) in (Union, UnionType):
        t = [e for e in get_args(t) if e is not NoneType][0]
    return t


def to_pyobject(value: Any, hint: type, *, from_sql: bool = False, from_mssql: bool = False, from_bson: bool = False, from_mysql: bool = False, from_chsql: bool = False) -> Any:
    """
    Convert a database-stored value back to its Python type.

    Handles type coercion for ``int``, ``float``, ``bool``, ``UUID``, ``datetime``,
    ``date``, ``time``, ``timedelta``, ``Decimal``, ``Enum``, and complex types
    (``dict``, ``list``, ``set``, ``tuple``) deserialized from JSON or BSON.

    For container types with element hints (e.g. ``list[date]``, ``dict[str, time]``),
    each element is recursively converted using the appropriate element type hint.

    ``datetime`` values are always returned timezone-aware; the provider flags
    select the read policy (see :func:`__apply_datetime_read_policy` for the
    per-provider behavior).  With no flags specified (the JSON path), aware
    values are treated as UTC.

    :param value: The raw value from the database.
    :param hint: The type hint for the field (e.g. ``Optional[str]`` or ``list[date]``).
    :param from_sql: If True, the value came from SQLite.
    :param from_mssql: If True, the value came from SQL Server.
    :param from_bson: If True, the value came from MongoDB.
    :param from_mysql: If True, the value came from MySQL.
    :param from_chsql: If True, the value came from ClickHouse.
    :return: The value converted to the appropriate Python type.
    """
    if value in (None, NoneType, 'null', 'NULL'):
        return None
    hint = deunionize(hint)
    if hint == int and isinstance(value, str):
        return int(value)
    elif hint == float and isinstance(value, str):
        return float(value)
    elif hint == bool:
        return True if value in ('1', 'TRUE', 'true', 'True', 1, True) else False
    elif hint == UUID and isinstance(value, str):
        return UUID(value)
    elif hint == datetime and isinstance(value, str):
        return __apply_datetime_read_policy(_parse_datetime_iso(value), from_sql, from_mssql, from_bson, from_mysql, from_chsql)
    elif hint == datetime and isinstance(value, datetime):
        return __apply_datetime_read_policy(value, from_sql, from_mssql, from_bson, from_mysql, from_chsql)
    elif hint == date and isinstance(value, datetime):
        return value.date()
    elif hint == date and isinstance(value, str):
        return date.fromisoformat(value)
    elif hint == time and isinstance(value, str):
        tm = _parse_time_iso(value)
        if tm.tzinfo is not None:
            return tm.replace(tzinfo=timezone.utc)
        return tm
    elif hint == time and isinstance(value, time):
        return value
    elif hint == timedelta and isinstance(value, int):
        return timedelta(microseconds=value)
    elif hint == Decimal:
        if isinstance(value, str):
            return Decimal(value)
        elif isinstance(value, Decimal):
            return value
        else:
            return Decimal(value)
    elif inspect.isclass(hint) and issubclass(hint, Enum):
        return hint(value)
    else:
        org = get_origin(hint)
        org = org if org is not None else hint
        if org in (Mapping, dict, list, set, tuple) and isinstance(value, str):
            d = __from_json(value)
            if not isinstance(d, org):
                d = hint(d)  # type: ignore[call-arg]
            return d
        elif org in (list, tuple, set):
            args = get_args(hint)
            if args:
                element_hint = args[0]
                if isinstance(value, (list, tuple, set)):
                    if element_hint is not Any:
                        if org is tuple:
                            return tuple(to_pyobject(v, element_hint) for v in value)
                        elif org is set:
                            return {to_pyobject(v, element_hint) for v in value}
                        else:
                            return [to_pyobject(v, element_hint) for v in value]
                    else:
                        return value
            else:
                return value
        elif org in (Mapping, dict):
            args = get_args(hint)
            if len(args) >= 2:
                key_hint, value_hint = args[0], args[1]
                if isinstance(value, dict):
                    if key_hint is not Any and value_hint is not Any:
                        return {to_pyobject(k, key_hint): to_pyobject(v, value_hint) for k, v in value.items()}
                    else:
                        return value
            else:
                return value
        else:
            return value


def _to_json_value(value: Any) -> Any:
    """Convert a single top-level value to a JSON-serializable form for standard json.dumps()."""
    if value in (None, NoneType, 'null', 'NULL'):
        return None
    if isinstance(value, datetime):
        # Naive values are treated as UTC; aware values keep their offset (UTC renders with 'Z').
        return _iso_z(ensure_utc_aware(value))
    elif isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, time):
        if value.tzinfo is not None:
            return _utc_z_time(value)
        else:
            return value.isoformat()
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, set):
        return list(value)
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, timedelta):
        return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
    # For lists, tuples, dicts: return as-is (preserves nested type round-trips)
    return value


def to_bsonobject(value: Any, hint: type | None = None) -> Any:
    """
    Convert a value for MongoDB BSON storage.

    Unlike :func:`_to_json_value`, this leaves types that BSON supports natively
    as their Python equivalents — PyMongo handles the rest:

    - ``datetime.datetime`` is normalized to aware UTC (BSON stores the UTC instant;
      timezone-aware values are converted via ``astimezone`` and naive values are
      treated as UTC)
    - ``datetime.date`` is converted to a midnight ``datetime`` for storage
    - ``datetime.time`` is converted to an ISO 8601 string ("HH:MM:SS.ffffff")
    - ``uuid.UUID`` is left as a Python ``UUID`` object (BSON binary)
    - ``set`` values are converted to ``list`` (BSON arrays)
    - ``list``/``tuple``/``dict`` are recursively serialized element-by-element

    When ``hint`` is provided, container element hints are extracted and used
    to convert each element (e.g. ``list[date]`` converts each element via
    ``to_bsonobject(v, date)`` rather than relying on runtime ``isinstance``).

    :param value: The Python value to convert.
    :param hint: Optional type hint (e.g. ``list[date]``).
    :return: A BSON-compatible value.
    """
    if value in (None, NoneType, 'null', 'NULL'):
        return None
    if isinstance(value, datetime):
        return assume_utc(value)
    elif isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    elif isinstance(value, time):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return str(value)
    # UUID: leave as UUID object — PyMongo handles native BSON binary
    elif isinstance(value, set):
        return [to_bsonobject(v) for v in value]
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, timedelta):
        return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
    elif isinstance(value, list):
        args = get_args(hint) if hint else ()
        if args:
            element_hint = args[0]
            return [to_bsonobject(v, element_hint) for v in value]
        return [to_bsonobject(v) for v in value]
    elif isinstance(value, tuple):
        args = get_args(hint) if hint else ()
        if args:
            element_hint = args[0]
            return tuple(to_bsonobject(v, element_hint) for v in value)
        return tuple(to_bsonobject(v) for v in value)
    elif isinstance(value, dict):
        args = get_args(hint) if hint else ()
        if len(args) >= 2:
            key_hint, value_hint = args[0], args[1]
            return {to_bsonobject(k, key_hint): to_bsonobject(v, value_hint) for k, v in value.items()}
        return {k: to_bsonobject(v) for k, v in value.items()}
    return value


def __to_sql_object_impl(value: Any, hint: type, dt_to_store: Callable[[datetime], datetime], uuid_to_store: Callable[[UUID], str]) -> Any:
    """
    Shared implementation for the SQL-family object converters
    (:func:`to_sqlobject`, :func:`to_mysql_object`, :func:`to_chsql_object`,
    :func:`to_mssql_object`).

    :param value: The Python value to convert.
    :param hint: The type hint for the field.
    :param dt_to_store: The datetime policy for the target DBMS.
    :param uuid_to_store: The UUID rendering for the target DBMS.
    :return: The DBMS-compatible value.
    """
    if value in (None, NoneType, 'null', 'NULL'):
        return None
    hint = deunionize(hint)
    if get_origin(hint) in (Mapping, dict, list, set, tuple):
        value = __to_json(value)
        return value if value != 'null' and value != '' else None
    elif hint == UUID:
        return uuid_to_store(value)
    elif hint == datetime:
        return dt_to_store(value)
    elif hint == date:
        return value.isoformat()
    elif hint == time:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return _utc_z_time(value)
    elif hint == timedelta:
        return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
    elif hint == bool:
        return int(value is True)
    elif inspect.isclass(hint) and issubclass(hint, Enum):
        return value.value
    else:
        return value


def to_sqlobject(value: Any, hint: type) -> Any:
    """
    Convert a Python value to a SQLite-compatible representation.

    ``datetime`` values are stored with offset information preserved:
    timezone-aware values pass through unchanged and naive values are
    treated as UTC (tagged via ``replace``, no change to the instant).

    Also handles conversion of ``UUID`` to hex, ``dict``/``list``/``set``/``tuple`` to JSON,
    ``bool`` to int, ``timedelta`` to microseconds, ``Enum`` to value, and ``Decimal`` to string.

    :param value: The Python value to convert.
    :param hint: The type hint for the field.
    :return: A SQLite-compatible value (e.g. datetime -> aware datetime, dict -> JSON).
    """
    return __to_sql_object_impl(value, hint, ensure_utc_aware, lambda uuid_value: uuid_value.hex)


def to_mysql_object(value: Any, hint: type) -> Any:
    """
    Convert a Python value to a MySQL-compatible representation.

    MySQL cannot store offset information, so ``datetime`` values are stored
    as UTC: timezone-aware values are converted via ``astimezone`` and naive
    values are treated as UTC (tagged via ``replace``, no change to the
    instant).

    Also handles conversion of ``UUID`` to hex, ``dict``/``list``/``set``/``tuple`` to JSON,
    ``bool`` to int, ``timedelta`` to microseconds, ``Enum`` to value, and ``Decimal`` to string.

    :param value: The Python value to convert.
    :param hint: The type hint for the field.
    :return: A MySQL-compatible value (e.g. datetime -> UTC datetime, dict -> JSON).
    """
    return __to_sql_object_impl(value, hint, assume_utc, lambda uuid_value: uuid_value.hex)


def to_chsql_object(value: Any, hint: type) -> Any:
    """
    Convert a Python value to a ClickHouse-compatible representation.

    ClickHouse cannot store offset information with plain ``DateTime64``
    columns, so ``datetime`` values are stored as UTC: timezone-aware values
    are converted via ``astimezone`` and naive values are treated as UTC
    (tagged via ``replace``, no change to the instant).

    Also handles conversion of ``UUID`` to hex, ``dict``/``list``/``set``/``tuple`` to JSON,
    ``bool`` to int, ``timedelta`` to microseconds, ``Enum`` to value, and ``Decimal`` to string.

    :param value: The Python value to convert.
    :param hint: The type hint for the field.
    :return: A ClickHouse-compatible value (e.g. datetime -> UTC datetime, dict -> JSON).
    """
    return __to_sql_object_impl(value, hint, assume_utc, lambda uuid_value: uuid_value.hex)


def __mssql_datetime_write_policy(dt: datetime) -> datetime:
    """
    Select the MSSQL write policy for a datetime value.

    With the default ``DATETIMEOFFSET`` storage type, timezone-aware values
    pass through unchanged (offsets are stored) and naive values are tagged
    as UTC (no change to the instant); with any other type configured via
    ``DEEV__MSSQL__DATETIME_TYPE``, all values are normalized to UTC (naive
    values are treated as UTC).
    """
    if get_mssql_datetime_type() == 'DATETIMEOFFSET':
        return ensure_utc_aware(dt)
    return assume_utc(dt)


def to_mssql_object(value: Any, hint: type) -> Any:
    """
    Convert a Python value to a SQL Server-compatible representation.

    Like :func:`to_sqlobject` but for SQL Server's ``UNIQUEIDENTIFIER`` type,
    which stores UUIDs in standard hyphenated format (``str(uuid)``) instead of hex.

    The ``datetime`` policy depends on the ``DEEV__MSSQL__DATETIME_TYPE``
    setting: with the default ``DATETIMEOFFSET`` type, timezone-aware values
    pass through unchanged (offsets are stored) and naive values are tagged
    as UTC; with any other type (e.g. ``DATETIME2``), all values are
    normalized to UTC.  See
    :func:`deev.translation.datetime_utils.get_mssql_datetime_type`.

    Also handles conversion of ``UUID`` to hyphenated string,
    ``dict``/``list``/``set``/``tuple`` to JSON, ``bool`` to int, ``timedelta`` to microseconds,
    ``Enum`` to value, and ``Decimal`` to string.

    :param value: The Python value to convert.
    :param hint: The type hint for the field.
    :return: A SQL Server-compatible value.
    """
    return __to_sql_object_impl(value, hint, __mssql_datetime_write_policy, str)


def splat_mssql(entity: object, attrs: list[str] | None = None) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict, mapping values to SQL Server-compatible objects (see :func:`to_mssql_object`).

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :return: The resulting splat.
    """
    result = dict[str, Any]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_hint in entity_spec.attrs.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
            if hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                result[attr_name] = to_mssql_object(attr_value, attr_hint)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def splat_sqlite(entity: object, attrs: list[str] | None = None) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict, mapping values to SQLite-compatible objects (see :func:`to_sqlobject`).

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :return: The resulting splat.
    """
    result = dict[str, Any]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_hint in entity_spec.attrs.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
            if hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                result[attr_name] = to_sqlobject(attr_value, attr_hint)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def splat_mysql(entity: object, attrs: list[str] | None = None) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict, mapping values to MySQL-compatible objects (see :func:`to_mysql_object`).

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :return: The resulting splat.
    """
    result = dict[str, Any]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_hint in entity_spec.attrs.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
            if hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                result[attr_name] = to_mysql_object(attr_value, attr_hint)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def splat_chsql(entity: object, attrs: list[str] | None = None) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict, mapping values to ClickHouse-compatible objects (see :func:`to_chsql_object`).

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :return: The resulting splat.
    """
    result = dict[str, Any]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_hint in entity_spec.attrs.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
            if hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                result[attr_name] = to_chsql_object(attr_value, attr_hint)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def splat_mongodb(entity: object, attrs: list[str] | None = None) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict, mapping values to BSON-compatible objects for MongoDB (see :func:`to_bsonobject`).

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :return: The resulting splat.
    """
    result = dict[str, Any]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_hint in entity_spec.attrs.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
            if hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                result[attr_name] = to_bsonobject(attr_value, attr_hint)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def splat_json(entity: object, attrs: list[str] | None = None) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict, mapping values to JSON-serializable objects (see :func:`_to_json_value`).

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :return: The resulting splat.
    """
    result = dict[str, Any]()
    t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_hint in entity_spec.attrs.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
            if hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                result[attr_name] = _to_json_value(attr_value)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def splat(entity: object, attrs: list[str] | None = None, to_sql: bool = False, to_bson: bool = False, to_mssql: bool = False, to_mysql: bool = False, to_chsql: bool = False) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict.

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :param to_sql: If True, destination values need to be mapped to SQLite-compatible objects.
    :param to_bson: If True, destination values need to be mapped to bson-compatible objects (for MongoDB).
    :param to_mssql: If True, destination values need to be mapped to SQL Server objects.
    :param to_mysql: If True, destination values need to be mapped to MySQL-compatible objects.
    :param to_chsql: If True, destination values need to be mapped to ClickHouse-compatible objects.
    :return: The resulting splat.
    :raises ValueError: If more than one destination mapping flag is specified.
    """
    if sum((to_sql, to_bson, to_mssql, to_mysql, to_chsql)) > 1:
        raise ValueError('Only one of `to_sql`, `to_bson`, `to_mssql`, `to_mysql`, `to_chsql` may be specified.')
    if to_mssql:
        return splat_mssql(entity, attrs)
    if to_sql:
        return splat_sqlite(entity, attrs)
    if to_mysql:
        return splat_mysql(entity, attrs)
    if to_chsql:
        return splat_chsql(entity, attrs)
    if to_bson:
        return splat_mongodb(entity, attrs)
    return splat_json(entity, attrs)


def hydrate_mssql(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None) -> Any:
    """
    Hydrates an entity in-place from a "splat," mapping values from SQL Server objects to python objects (see :func:`to_pyobject`).

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :return: The original entity, hydrated.
    """
    t: type
    if isinstance(entity, type):
        t = entity
        entity = entity()
    else:
        t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_value in data.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
        hint = entity_spec.attrs.get(attr_name, None)
        if hint is not None:
            setattr(entity, attr_name, to_pyobject(attr_value, hint, from_mssql=True))
    return entity


def hydrate_sqlite(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None) -> Any:
    """
    Hydrates an entity in-place from a "splat," mapping values from SQLite objects to python objects (see :func:`to_pyobject`).

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :return: The original entity, hydrated.
    """
    t: type
    if isinstance(entity, type):
        t = entity
        entity = entity()
    else:
        t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_value in data.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
        hint = entity_spec.attrs.get(attr_name, None)
        if hint is not None:
            setattr(entity, attr_name, to_pyobject(attr_value, hint, from_sql=True))
    return entity


def hydrate_mysql(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None) -> Any:
    """
    Hydrates an entity in-place from a "splat," mapping values from MySQL objects to python objects (see :func:`to_pyobject`).

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :return: The original entity, hydrated.
    """
    t: type
    if isinstance(entity, type):
        t = entity
        entity = entity()
    else:
        t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_value in data.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
        hint = entity_spec.attrs.get(attr_name, None)
        if hint is not None:
            setattr(entity, attr_name, to_pyobject(attr_value, hint, from_mysql=True))
    return entity


def hydrate_chsql(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None) -> Any:
    """
    Hydrates an entity in-place from a "splat," mapping values from ClickHouse objects to python objects (see :func:`to_pyobject`).

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :return: The original entity, hydrated.
    """
    t: type
    if isinstance(entity, type):
        t = entity
        entity = entity()
    else:
        t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_value in data.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
        hint = entity_spec.attrs.get(attr_name, None)
        if hint is not None:
            setattr(entity, attr_name, to_pyobject(attr_value, hint, from_chsql=True))
    return entity


def hydrate_mongodb(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None) -> Any:
    """
    Hydrates an entity in-place from a "splat," mapping values from BSON objects (MongoDB, UUIDs are already UUID objects) to python objects (see :func:`to_pyobject`).

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :return: The original entity, hydrated.
    """
    t: type
    if isinstance(entity, type):
        t = entity
        entity = entity()
    else:
        t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_value in data.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
        hint = entity_spec.attrs.get(attr_name, None)
        if hint is not None:
            setattr(entity, attr_name, to_pyobject(attr_value, hint, from_bson=True))
    return entity


def hydrate_json(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None) -> Any:
    """
    Hydrates an entity in-place from a "splat," mapping values from JSON-serialized objects to python objects (see :func:`to_pyobject`).

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :return: The original entity, hydrated.
    """
    t: type
    if isinstance(entity, type):
        t = entity
        entity = entity()
    else:
        t = type(entity)
    entity_spec = get_entity_spec(t)
    for attr_name, attr_value in data.items():
        if attrs is not None and attr_name not in attrs:
            continue
        field_spec = entity_spec.fields.get(attr_name, None)
        if field_spec is not None:
            if field_spec.mapped is False:
                continue
        hint = entity_spec.attrs.get(attr_name, None)
        if hint is not None:
            setattr(entity, attr_name, to_pyobject(attr_value, hint))
    return entity


def hydrate(entity: object | type, data: dict[str, Any], attrs: list[str] | None = None, from_sql: bool = False, from_mssql: bool = False, from_bson: bool = False, from_mysql: bool = False, from_chsql: bool = False) -> Any:
    """
    Hydrates an entity in-place from a "splat."

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :param from_sql: If True, source values are presumed to be SQLite objects that need to be mapped to python objects.
    :param from_mssql: If True, source values are presumed to be SQL Server objects that need to be mapped to python objects.
    :param from_bson: If True, source values are presumed to be BSON objects from MongoDB (UUIDs are already UUID objects).
    :param from_mysql: If True, source values are presumed to be MySQL objects that need to be mapped to python objects.
    :param from_chsql: If True, source values are presumed to be ClickHouse objects that need to be mapped to python objects.
    :return: The original entity, hydrated.
    :raises ValueError: If more than one source mapping flag is specified.
    """
    if sum((from_sql, from_mssql, from_bson, from_mysql, from_chsql)) > 1:
        raise ValueError('Only one of `from_sql`, `from_mssql`, `from_bson`, `from_mysql`, `from_chsql` may be specified.')
    if from_mssql:
        return hydrate_mssql(entity, data, attrs)
    if from_sql:
        return hydrate_sqlite(entity, data, attrs)
    if from_mysql:
        return hydrate_mysql(entity, data, attrs)
    if from_chsql:
        return hydrate_chsql(entity, data, attrs)
    if from_bson:
        return hydrate_mongodb(entity, data, attrs)
    return hydrate_json(entity, data, attrs)


__all__ = [
    'configure_serialization',
    'deunionize',
    'hydrate',
    'hydrate_mongodb',
    'hydrate_chsql',
    'hydrate_json',
    'hydrate_mssql',
    'hydrate_mysql',
    'hydrate_sqlite',
    'splat',
    'splat_mongodb',
    'splat_chsql',
    'splat_json',
    'splat_mssql',
    'splat_mysql',
    'splat_sqlite',
    'to_bsonobject',
    'to_chsql_object',
    'to_mssql_object',
    'to_mysql_object',
    'to_pyobject',
    'to_sqlobject',
]
