# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import base64
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
from types import NoneType
from typing import Any, Callable, Mapping, Optional, Union, get_args, get_origin
from uuid import UUID

from .entities import get_entity_spec


def _parse_datetime_iso(value: str) -> datetime:
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    return datetime.fromisoformat(value)


def _parse_time_iso(value: str) -> time:
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    return time.fromisoformat(value)


class DeevJsonDecoder(json.JSONDecoder):

    def decode(self, s: str, _w: Optional[Callable[..., Any]] = None) -> Any:
        return self.__decode(super().decode(s), _w)

    def __decode(self, obj: Any, _w: Optional[Callable[..., Any]] = None) -> Any:
        if isinstance(obj, str):
            tick_index = obj.find('`')
            if tick_index > 0:
                ident = obj[:tick_index]
                remand = obj[tick_index + 1:]
                match ident:
                    case 'dt':
                        return _parse_datetime_iso(remand)
                    case 'date':
                        return date.fromisoformat(remand)
                    case 'time':
                        return _parse_time_iso(remand)
                    case 'r':
                        return Decimal(remand)
                    case 'u':
                        return UUID(remand)
                    case 's':
                        return set(self.decode(remand))
                    case 't':
                        return tuple(self.decode(remand))
                    case 'b':
                        return base64.b64decode(remand)
        if isinstance(obj, dict):
            return {
                k: self.__decode(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [
                self.__decode(v)
                for v in obj
            ]
        return obj


def _utc_z(dt: datetime) -> str:
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%S') + (
        ('.%06d' % utc_dt.microsecond) if utc_dt.microsecond else ''
    ) + 'Z'


def _utc_z_time(t: time) -> str:
    return t.strftime('%H:%M:%S') + (
        ('.%06d' % t.microsecond) if t.microsecond else ''
    ) + 'Z'


class DeevJsonEncoder(json.JSONEncoder):

    def __process(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is not None:
                return f'dt`{_utc_z(obj)}'
            else:
                return f'dt`{obj.isoformat()}'
        elif isinstance(obj, date):
            return f'date`{obj.isoformat()}'
        elif isinstance(obj, time):
            if obj.tzinfo is not None:
                return f'time`{_utc_z_time(obj)}'
            else:
                return f'time`{obj.isoformat()}'
        elif isinstance(obj, Decimal):
            return f'r`{str(obj)}'
        elif isinstance(obj, UUID):
            return f'u`{str(obj)}'
        elif isinstance(obj, set):
            return f's`{self.encode([e for e in obj])}'
        elif isinstance(obj, tuple):
            return f't`{self.encode([e for e in obj])}'
        elif isinstance(obj, bytes):
            return f'b`{base64.b64encode(obj).decode("ascii")}'
        elif isinstance(obj, list):
            return [self.__process(e) for e in obj]
        elif isinstance(obj, dict):
            return {k: self.__process(v) for k, v in obj.items()}
        else:
            return obj

    def encode(self, o: Any) -> str:
        return super().encode(self.__process(o))


__json_encoder: type[json.JSONEncoder] = DeevJsonEncoder
__json_decoder: type[json.JSONDecoder] = DeevJsonDecoder
__serializer: Optional[Callable[[Any], str]] = None
__deserializer: Optional[Callable[[Any], str]] = None


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


def configure_serialization(  # pragma: no cover
    *,
    encoder: Optional[type[json.JSONEncoder]] = None,
    decoder: Optional[type[json.JSONDecoder]] = None,
    serializer: Optional[Callable[[Any], str]] = None,
    deserializer: Optional[Callable[[str], Any]] = None
) -> None:
    """
    Set json encoders/decoders used for sql translations.

    This because complex types such as lists, tuples, dicts, Decimals, etc/etc being stored to db get serialized (stored as a string.)

    When the default serializer encounters an unsupported type the serialization fails.

    This provides you a mechanism to customize serialization.

    If you wish to extend the default behavior without re-implementing it all, you can inherit from the exposed DeevJsonEncoder and DeevJsonDecoder, then pass your subclassed versions in.  If your work is not proprietary, consider submitting an issue on github to have the support formally added.

    Alternatively, if you want to wholesale swap the serializer (something other than json, or a json impl you prefer) you can provide `serializer` and `deserializer` callbacks instead.  If you set new serializer/deserializer callbacks the encoders will not be used (and, detecting that serializer/deserializer are custom will throw on any attempt to set new encoders.)
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
    if get_origin(t) is Union:
        t = [e for e in get_args(t) if e is not NoneType][0]
    return t


def to_pyobject(value: Any, hint: type) -> Any:
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
        dt = _parse_datetime_iso(value)
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    elif hint == date and isinstance(value, str):
        return date.fromisoformat(value)
    elif hint == time and isinstance(value, str):
        tm = _parse_time_iso(value)
        if tm.tzinfo is not None:
            return tm.replace(tzinfo=timezone.utc)
        return tm
    elif hint == timedelta and isinstance(value, int):
        return timedelta(microseconds=value)
    elif hint == Decimal:
        if isinstance(value, str):
            return Decimal(value)
        elif isinstance(value, Decimal):
            return value
        else:
            return Decimal(value)
    else:
        org = get_origin(hint)
        org = org if org is not None else hint
        if org in (Mapping, dict, list, set, tuple) and isinstance(value, str):
            d = __from_json(value)
            if not isinstance(d, org):
                d = hint(d)
            return d
        else:
            return value


def _to_json_value(value: Any) -> Any:
    """Convert a single top-level value to a JSON-serializable form for standard json.dumps()."""
    if value in (None, NoneType, 'null', 'NULL'):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return _utc_z(value)
        else:
            return value.isoformat()
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
    # For lists, tuples, dicts: return as-is (preserves nested type round-trips)
    return value


def to_sqlobject(value: Any, hint: type) -> Any:
    if value in (None, NoneType, 'null', 'NULL'):
        return None
    hint = deunionize(hint)
    if get_origin(hint) in (Mapping, dict, list, set, tuple):
        value = __to_json(value)
        return value if value != 'null' and value != '' else None
    elif hint == datetime:
        if value.tzinfo is not None:
            return _utc_z(value)
        else:
            u = value.replace(tzinfo=timezone.utc)
            return _utc_z(u)
    elif hint == date:
        return value.isoformat()
    elif hint == time:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return _utc_z_time(value)
    elif hint == timedelta:
        return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
    elif hint == UUID:
        return str(value)
    elif hint == bool:
        return int(value is True)
    else:
        return value


def splat(entity: object, attrs: Optional[list[str]] = None, to_sql: bool = False) -> dict[str, Any]:
    """
    Splatter entity attributes/fields into a dict.

    :param entity: The entity to splatter.
    :param attrs: Specify which attrs/fields to splatter, otherwise splatter all.
    :param to_sql: If True, destination values need to be mapped to sql objects.
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
                # NOTE: this edge case is handled by way of __getattribute__ logic now
                # if attr_value is None and field_spec is not None and field_spec.nullable is not True:
                #     # NOTE: twe do NOT translate NULLs unless spec'd to do so.
                #     continue
                if to_sql:
                    result[attr_name] = to_sqlobject(attr_value, attr_hint)
                else:
                    result[attr_name] = _to_json_value(attr_value)
            elif field_spec.nullable:
                result[attr_name] = None
    return result


def hydrate(entity: object | type, data: dict[str, Any], attrs: Optional[list[str]] = None, from_sql: bool = False) -> Any:
    """
    Hydrates an entity in-place from a "splat."

    :param entity: The entity to hydrate, or a type specifier of an entity to create and then hydrate.
    :param data: The data to hydrate.
    :param attrs: Specify which attrs/props to hydrate, otherwise hydrates all.
    :param from_sql: If True, source values are presumed to be sql objects that need to be mapped to python objects.
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


__all__ = [
    'DeevJsonEncoder',
    'DeevJsonDecoder',
    'configure_serialization',
    'deunionize',
    'hydrate',
    'splat',
    'to_pyobject',
    'to_sqlobject'
]
