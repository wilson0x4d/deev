# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Mapping, get_origin
from uuid import UUID

from ..common.db_error import DbError
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec
from ..translation import deunionize


class MongoTypeMapper(DbTypeMapper):
    __entity_spec: EntitySpec
    __pytype_map: dict[Any, str]

    def __init__(self, entity_spec: EntitySpec) -> None:
        self.__entity_spec = entity_spec
        self.__pytype_map = {
            int: 'int32',
            float: 'double',
            Decimal: 'decimal',
            str: 'string',
            bool: 'bool',
            dict: 'object',
            list: 'array',
            Mapping: 'object',
            tuple: 'array',
            set: 'array',
            UUID: 'string',
            date: 'date',
            datetime: 'datetime',
            time: 'time',
            timedelta: 'int64'
        }

    def get_provider_type(self, field_name: str) -> str:
        """
        Get the provider type string (e.g., BSON type identifier) needed to represent
        an entity field in the underlying collection.
        :param field_spec: The "Entity Field Spec".
        :return: The provider type string.
        """
        field_spec = self.__entity_spec.fields.get(field_name, None)
        if field_spec is not None:
            if field_spec.dbtype is not None:
                return field_spec.dbtype
            field_type = self.__entity_spec.attrs.get(field_name, None)
            if field_type is not None:
                field_type = deunionize(field_type)
                mapped_dbtype = self.__pytype_map.get(field_type, None)
                if mapped_dbtype is not None:
                    return mapped_dbtype
                org = get_origin(field_type)
                if org is not None and org in (dict, Mapping, list, tuple, set):
                    mapped_dbtype = self.__pytype_map.get(org, None)
                    if mapped_dbtype is not None:
                        return mapped_dbtype
        else:
            raise DbError(f'Non-existent field "{field_name}" for "{self.__entity_spec.table_name}".')
        raise DbError(f'Unsupported field "{field_name}" having type "{field_type}".')


__all__ = ['MongoTypeMapper']
