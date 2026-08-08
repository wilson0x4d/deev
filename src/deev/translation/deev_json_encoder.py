# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timezone
import json
import base64
from decimal import Decimal
from typing import Any
from uuid import UUID


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


__all__ = ['DeevJsonEncoder']
