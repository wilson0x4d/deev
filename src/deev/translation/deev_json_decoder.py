# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time
from decimal import Decimal
import json
import base64
from typing import Any, Callable, Optional
from uuid import UUID


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


__all__ = ['DeevJsonDecoder']
