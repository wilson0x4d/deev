# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping, TypeVar, cast, get_origin

from ..common.db_error import DbError
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec
from ..entities.entity_field_spec import EntityFieldSpec
from ..translation import deunionize

if TYPE_CHECKING:
    from uuid import UUID


TEntity = TypeVar('TEntity')


class ClickHouseTypeMapper(DbTypeMapper):
    __entity_spec: EntitySpec
    __pytype_map: dict[Any, str]

    def __init__(self, entity_spec: EntitySpec) -> None:
        self.__entity_spec = entity_spec
        self.__pytype_map = {
            int: 'Int64',
            float: 'Float64',
            Decimal: 'Decimal(20, 10)',
            str: 'String',
            bool: 'Bool',
            dict: 'String',
            list: 'String',
            Mapping: 'String',
            tuple: 'String',
            set: 'String',
            date: 'Date32',
            datetime: 'DateTime64(6)',
            time: 'String',
            timedelta: 'Int64'
        }

    def __make_nullable(self, type_str: str, field_spec: EntityFieldSpec) -> str:
        if field_spec.nullable:
            return f'Nullable({type_str})'
        return type_str

    def __handle_string_type(self, field_type: type, field_spec: EntityFieldSpec) -> str:
        max_len: int | float | None = getattr(field_spec, 'max', None)
        min_val: int | float | None = getattr(field_spec, 'min', None)
        int_max: int | float | None
        if max_len is not None and max_len == min_val:
            int_max = int(max_len)
            if int_max <= 256:
                return self.__make_nullable(f'FixedString({int_max})', field_spec)
            return self.__make_nullable('String', field_spec)
        if max_len is not None:
            int_max = int(max_len) if isinstance(max_len, float) and max_len == int(max_len) else max_len
            if int_max <= 256:
                return self.__make_nullable(f'FixedString({int_max})', field_spec)
            return self.__make_nullable('String', field_spec)
        return self.__make_nullable('String', field_spec)

    def get_provider_type(self, field_name: str) -> str:
        field_spec: EntityFieldSpec | None = self.__entity_spec.fields.get(field_name, None)
        if field_spec is not None:
            if field_spec.dbtype is not None:
                return field_spec.dbtype
            field_type = self.__entity_spec.attrs.get(field_name, None)
            if field_type is not None:
                field_type = deunionize(field_type)
                mapped_dbtype: str | None = self.__pytype_map.get(field_type, None)
                if mapped_dbtype is not None:
                    if field_type is str:
                        return self.__handle_string_type(field_type, field_spec)
                    elif field_type in (datetime, date):
                        return self.__make_nullable(mapped_dbtype, field_spec)
                    else:
                        return self.__make_nullable(mapped_dbtype, field_spec)
                org = get_origin(field_type)
                if org is not None and org in (dict, Mapping, list, tuple, set):
                    mapped_dbtype = self.__pytype_map.get(org, None)
                    if mapped_dbtype is not None:
                        return self.__make_nullable(mapped_dbtype, field_spec)
        else:
            raise DbError(f'Non-existent field "{field_name}" for "{self.__entity_spec.table_name}".')
        return 'String'
