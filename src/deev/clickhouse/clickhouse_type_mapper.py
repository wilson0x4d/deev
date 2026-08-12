# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping as AbcMapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping, TypeVar, get_args, get_origin

from ..common.db_error import DbError
from ..common.db_type_mapper import DbTypeMapper
from ..entities import EntitySpec
from ..entities.entity_field_spec import EntityFieldSpec
from ..translation import deunionize

if TYPE_CHECKING:
    from uuid import UUID


TEntity = TypeVar('TEntity')


class ClickHouseNativeMapError(Exception):
    """Raised when a Python type containing 'Any' is used in a generic collection context
    where a native ClickHouse type would be required but cannot be resolved."""
    pass


class ClickHouseTypeMapper(DbTypeMapper):
    __entity_spec: EntitySpec
    __pytype_map: dict[Any, str]

    # Origin types that should be mapped to native ClickHouse types
    __native_origin_map: dict[Any, str] = {
        list: 'Array',
        set: 'Array',
        dict: 'Map',
        Mapping: 'Map',
        AbcMapping: 'Map',
        tuple: 'Tuple',
    }

    # Origin types for which bare (unparameterized) use falls back to String
    __fallback_to_string_origins: set[Any] = {list, set, dict, Mapping, AbcMapping, tuple}

    def __init__(self, entity_spec: EntitySpec) -> None:
        self.__entity_spec = entity_spec
        self.__pytype_map = {
            int: 'Int64',
            float: 'Float64',
            Decimal: 'Decimal128(18)',
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
        return self.__make_nullable('String', field_spec)

    def __get_native_type(self, field_type: Any, path: str = '') -> str:
        """
        Recursively resolve a Python type to its ClickHouse native equivalent.
        Raises ClickHouseNativeMapError if 'Any' is encountered in a position
        that requires a concrete ClickHouse type.
        """
        origin = get_origin(field_type)
        if origin is not None:
            if origin in self.__native_origin_map:
                args = get_args(field_type)
                native_base = self.__native_origin_map[origin]
                if native_base == 'Array':
                    # Array is a single-argument type (list[T], set[T])
                    if len(args) != 1:
                        raise ClickHouseNativeMapError(
                            f'Type at "{path}" must specify a single type argument for '
                            f'list/set (got {len(args)}). Use e.g. list[int], not list.'
                        )
                    elem_type = args[0]
                    if elem_type is Any:
                        raise ClickHouseNativeMapError(
                            f'Type at "{path}" contains type parameter "Any". '
                            f'ClickHouse requires concrete types. Use e.g. list[str], not list[Any].'
                        )
                    mapped = self.__get_native_type(elem_type, f'{path}.elem')
                    return f'{native_base}({mapped})'
                elif native_base == 'Map':
                    # Map is a two-argument type (dict[K, V], Mapping[K, V])
                    if len(args) != 2:
                        raise ClickHouseNativeMapError(
                            f'Type at "{path}" must specify two type arguments for '
                            f'dict/Mapping (got {len(args)}). Use e.g. dict[str, int], not dict.'
                        )
                    key_type, val_type = args
                    if key_type is Any:
                        raise ClickHouseNativeMapError(
                            f'Key type at "{path}" is "Any". ClickHouse Map requires '
                            f'a concrete key type. Use e.g. dict[str, int], not dict[str, Any].'
                        )
                    if val_type is Any:
                        raise ClickHouseNativeMapError(
                            f'Value type at "{path}" is "Any". ClickHouse Map requires '
                            f'a concrete value type. Use e.g. dict[str, int], not dict[str, Any].'
                        )
                    mapped_key = self.__get_native_type(key_type, f'{path}.key')
                    mapped_val = self.__get_native_type(val_type, f'{path}.val')
                    return f'{native_base}({mapped_key}, {mapped_val})'
                elif native_base == 'Tuple':
                    if len(args) == 0:
                        raise ClickHouseNativeMapError(
                            f'Type at "{path}" is a bare tuple with no type parameters. '
                            f'ClickHouse Tuple requires at least one type argument.'
                        )
                    mapped_args = tuple(
                        self.__get_native_type(arg, f'{path}[{i}]')
                        for i, arg in enumerate(args)
                    )
                    return f'Tuple({", ".join(mapped_args)})'
        elif field_type is Any:
            raise ClickHouseNativeMapError(
                f'Found bare "Any" type at "{path}". ClickHouse requires concrete types. '
                f'Use a specific type instead (str, int, list, dict, etc.).'
            )
        # Primitive / simple type
        mapped_dbtype: str | None = self.__pytype_map.get(field_type, None)
        if mapped_dbtype is not None:
            return mapped_dbtype
        # Unknown simple type — fall back to String (this is safe for simple untyped fields)
        return 'String'

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
                # Check for generic types (list[T], dict[K, V], etc.)
                org = get_origin(field_type)
                if org is not None and org in self.__native_origin_map:
                    return self.__make_nullable(
                        self.__get_native_type(field_type, field_name), field_spec
                    )
                # Check for generic types that fall back to String (bare list, bare dict without args)
                if org is not None and org in self.__fallback_to_string_origins:
                    return self.__make_nullable('String', field_spec)
        else:
            raise DbError(f'Non-existent field "{field_name}" for "{self.__entity_spec.table_name}".')
        return 'String'
