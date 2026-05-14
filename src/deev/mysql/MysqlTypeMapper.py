# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Mapping, get_origin
from uuid import UUID

from ..common.DbError import DbError
from ..common.DbTypeMapper import DbTypeMapper
from ..entities import EntitySpec
from ..translation import deunionize


class MysqlTypeMapper(DbTypeMapper):

    __entity_spec: EntitySpec
    __pytype_map: dict[Any, str]

    def __init__(self, entity_spec: EntitySpec) -> None:
        self.__entity_spec = entity_spec
        self.__pytype_map = {
            int: 'BIGINT',
            float: 'DOUBLE',
            Decimal: 'DECIMAL(20,10)',
            str: 'VARCHAR(20)',
            bool: 'BIT',
            dict: 'MEDIUMTEXT',
            list: 'MEDIUMTEXT',
            Mapping: 'MEDIUMTEXT',
            tuple: 'MEDIUMTEXT',
            set: 'MEDIUMTEXT',
            UUID: 'CHAR(32)',
            date: 'DATE',
            datetime: 'DATETIME(6)',
            time: 'TIME(6)',
            timedelta: 'BIGINT'
        }

    def get_sqltype(self, field_name: str) -> str:
        """
        Get the SQL type (string) needed to represent an entity field in the underlying table.

        :param field_spec: The "Entity Field Spec".
        :return: The SQL type string.
        """
        # check field spec for an override
        field_spec = self.__entity_spec.fields.get(field_name, None)
        if field_spec is not None:
            if field_spec.sqltype is not None:
                return field_spec.sqltype
            # resolve from type hint
            field_type = self.__entity_spec.attrs.get(field_name, None)
            if field_type is not None:
                field_type = deunionize(field_type)
                if field_type is str:
                    if field_spec.min is not None and field_spec.min == field_spec.max:
                        return f'CHAR({field_spec.max})'
                    if field_spec.max is not None:
                        return f'VARCHAR({field_spec.max})'
                mapped_sqltype = self.__pytype_map.get(field_type, None)
                if mapped_sqltype is not None:
                    return mapped_sqltype
                org = get_origin(field_type)
                if org is not None and org in (dict, Mapping, list, tuple, set):
                    mapped_sqltype = self.__pytype_map.get(org, None)
                    if mapped_sqltype is not None:
                        return mapped_sqltype
        else:
            raise DbError(f'Non-existent field "{field_name}" for "{self.__entity_spec.table_name}".')
        raise DbError(f'Unsupported field "{field_name}" having type "{field_type}".')


__all__ = ['MysqlTypeMapper']
