# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities import IndexOptions, IndexOrder
from collections import defaultdict
import pymongo
from typing import Any, Generator, Generic, Optional, TypeVar, cast, get_args, get_origin

from ..common.DbContext import DbContext
from ..common.DbCursor import DbCursor
from ..common.DbError import DbError
from ..common.DbParams import DbParams
from ..common.DbTypeMapper import DbTypeMapper
from ..entities import EntitySpec, get_entity_spec
from ..translation import hydrate, splat, to_pyobject
from .MongoProxyCursor import _parse_sql_where
from .MongoTypeMapper import MongoTypeMapper


TEntity = TypeVar('TEntity')



class MongoTableAdapter(Generic[TEntity]):
    __column_names: str
    __context: DbContext
    __create_table: bool
    __cursor: DbCursor
    __database_name: str
    __entity_spec: EntitySpec
    __initialized: bool
    __dbtype_mapper: DbTypeMapper
    __table_name: Optional[str]
    __transaction_state: int

    def __init__(
        self,
        context: DbContext,
        *,
        create_table: Optional[bool] = False,
        table_name: Optional[str] = None
    ) -> None:
        self.__context = context
        self.__create_table = create_table is True
        self.__initialized = False
        self.__table_name = table_name
        self.__transaction_state = 0

        self.__database_name = self.__context.mongo_database_name  # type: ignore[missing-attribute, union-attr]

    def __deferred_init(self) -> None:
        if not self.__initialized:
            entity_type = self.__get_typearg(self)
            self.__entity_spec = get_entity_spec(entity_type)
            self.__column_names = ', '.join([f'`{k}`' for k in self.__entity_spec.fields.keys()])
            self.__dbtype_mapper = MongoTypeMapper(self.__entity_spec)
            self.__cursor = self.__context.cursor()
            self.__initialized = True
            if self.__create_table is True:
                self.create_table()

    @property
    def primary_key(self) -> tuple[str, ...]:
        return self.__entity_spec.primary_key

    @property
    def mongo_collection(self) -> pymongo.collection.Collection[Any]:
        # NOTE: this is a non-conformant property that we require for migration scripts (QOL), and must be retained.
        self.__deferred_init()
        return self.__context.mongo_database[  # type: ignore
            self.__table_name
            if self.__table_name is not None
            else self.__entity_spec.table_name
        ]

    def __get_pyobject(self, key: str, value: Any) -> Any:
        return to_pyobject(
            value,
            cast(type, self.__entity_spec.attrs.get(key)))

    def __get_typearg(self, obj: object) -> type:
        orig = getattr(obj, '__orig_class__', None)
        if orig is not None:
            args = get_args(orig)
            if args:
                return args[0]
        for base in obj.__class__.__mro__:
            for generic_base in getattr(base, '__orig_bases__', ()):
                if get_origin(generic_base) is MongoTableAdapter:
                    args = get_args(generic_base)
                    if args is not None and len(args) > 0:
                        return args[0]
        raise RuntimeError(
            f'Could not determine the entity type for {obj.__class__.__qualname__}. '
            'Instantiate via the generic alias, e.g. MongoTableAdapter[MyEntity]().'
        )

    def __get_collection_name(self) -> str:
        """Return the table/collection name (from explicit override or entity spec)."""
        return self.__table_name if self.__table_name is not None else self.__entity_spec.table_name

    def __get_database(self) -> pymongo.database.Database[Any]:
        """Return the pymongo database from the cursor's session."""
        mongo_session = getattr(self.__context.cursor(), 'mongo_session', None)  # type: ignore[union-attr]
        if mongo_session is None:
            raise DbError('Cursor does not have a mongo_session attribute.')
        return mongo_session._client[self.__database_name]  # type: ignore[attr-defined]

    def _get_collection(self) -> pymongo.collection.Collection[Any]:
        """Get the MongoDB collection for this adapter."""
        db = self.__get_database()
        return db[self.__get_collection_name()]

    def create_table(self) -> None:
        """Utility method for creating the target table."""
        self.__deferred_init()
        collection_name = self.__get_collection_name()
        connection = cast(pymongo.MongoClient[Any], getattr(self.__context, 'mongo_client', None))
        db = connection.get_database(self.__database_name)
        mongo_session = cast(pymongo.client_session.ClientSession, getattr(self.__context.cursor(), 'mongo_session', None))
        if collection_name not in db.list_collection_names():
            collection: pymongo.collection.Collection[Any]
            if len(self.primary_key) > 0:
                collection = db[collection_name]
            else:
                collection = db.create_collection(
                    name=collection_name,
                    session=None if mongo_session.in_transaction is not True else mongo_session,
                    check_exists=True
                    # TODO: implement validation as much as is possible between entity spec and mongodb
                    # validator=
                    # validationLevel=
                    # validationAction=
                )
            primary_key = {
                k: 1
                for k in self.primary_key
            }
            if len(primary_key) > 0:
                collection.create_index(
                    primary_key,
                    session=mongo_session,
                    unique=True,
                    name='pk'
                )
            # create indexes for all entity fields with `index` attributes
            index_groups = defaultdict[str, list[tuple[str, IndexOptions]]](list)
            index_attrs = defaultdict[str, dict[str, Any]](dict)
            for field_name, field_spec in self.__entity_spec.fields.items():
                if field_spec.index is not None:
                    assert isinstance(field_spec.index, IndexOptions)
                    index_groups[field_spec.index.name].append((field_name, field_spec.index))
                    index_groups[field_spec.index.name] = sorted(index_groups[field_spec.index.name])
                    index_attrs[field_spec.index.name]['unique'] = field_spec.unique is True
                    index_attrs[field_spec.index.name]['name'] = field_spec.index.name
            for index_name, index_group in index_groups.items():
                keys = [
                    (e[0], e[1].type if e[1].type is not None else pymongo.ASCENDING if e[1].direction is IndexOrder.ASCENDING else pymongo.DESCENDING)
                    for e in index_group
                ]
                collection.create_index(
                    keys=keys,
                    session=mongo_session,
                    comment=index_name,
                    **(index_attrs[index_name])
                )

    def commit(self) -> None:
        self.__context.commit()

    def rollback(self) -> None:
        self.__context.rollback()

    def __get_autoincrement(self) -> int:
        return cast(dict[str, Any], (
            cast(pymongo.MongoClient[Any], getattr(self.__context, 'mongo_client', None))
            .get_database(self.__database_name)["_deev"]  # type: ignore[missing-attribute]
            .find_one_and_update(
                {'_id': self.__table_name if self.__table_name is not None else self.__entity_spec.table_name},
                {'$inc': {'autoincrement': 1}},
                upsert=True,
                return_document=pymongo.ReturnDocument.AFTER
            )
        ))['autoincrement']

    def create(self, entity: Optional[TEntity] = None, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new record in the specified table with the provided attributes/values.
        :returns: the primary key of the created entity.
        """
        self.__deferred_init()
        data = (
            splat(entity, to_sql=False, to_bson=True)  # type: ignore[arg-type]
            if entity is not None
            else dict[str, Any]()
        )
        if kwargs:
            for k, v in kwargs.items():
                data[k] = v
        primary_key = {
            k: v
            for k, v in data.items()
            if k in self.__entity_spec.primary_key
        }
        collection = self._get_collection()
        if self.__entity_spec.has_autoincrement:
            # special handling for auto-increment columns
            if self.__entity_spec.primary_key[0] in data.keys():
                data.pop(self.__entity_spec.primary_key[0])
            # also requires an expensive operation
            pk_field = self.__entity_spec.primary_key[0]
            increment = self.__get_autoincrement()
            collection.insert_one(
                data | {
                    pk_field: increment
                }
            )
            primary_key = {
                pk_field: increment
            }
        else:
            collection.insert_one(data)
        return primary_key

    def read(self, **kwargs: Any) -> TEntity | None:
        """
        Reads a record from the specified table with the key represented by `kwargs`.
        """
        self.__deferred_init()
        primary_key = {
            k: v
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        result: dict[str, Any]
        collection = self._get_collection()
        raw_doc = collection.find_one(primary_key)
        if raw_doc is None:
            return None
        doc = {k: v for k, v in raw_doc.items() if k != '_id'}
        return hydrate(self.__entity_spec.entity_type, doc, from_bson=True)  # type: ignore[arg-type]

    def update(self, entity: TEntity) -> None:
        self.__deferred_init()
        entity_data = splat(entity, to_sql=False, to_bson=True)  # type: ignore[arg-type]
        primary_key = {
            k: v
            for k, v in entity_data.items()
            if k in self.__entity_spec.primary_key
        }
        collection = self._get_collection()
        update_fields = {k: v for k, v in entity_data.items() if k not in self.__entity_spec.primary_key}
        collection.update_one(primary_key, {'$set': update_fields})  # type: ignore[union-attr]

    def delete(self, **kwargs: Any) -> None:
        self.__deferred_init()
        primary_key = {
            k: v
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        collection = self._get_collection()
        collection.delete_one(primary_key)  # type: ignore[union-attr]

    def exists(self, **kwargs: Any) -> bool:
        self.__deferred_init()
        primary_key = {
            k: v
            for k, v in kwargs.items()
            if k in self.__entity_spec.primary_key
        }
        return self._get_collection().find_one(primary_key) is not None

    def upsert(self, entity: TEntity) -> dict[str, Any]:
        self.__deferred_init()
        data = splat(entity, to_sql=False, to_bson=True)  # type: ignore[arg-type]
        primary_key = {
            k: v
            for k, v in data.items()
            if k in self.__entity_spec.primary_key
        }
        collection = self._get_collection()
        if self.__entity_spec.has_autoincrement:
            # special handling for auto-increment columns (while implemented, you absolutely should not be using this)
            if self.__entity_spec.primary_key[0] in data.keys():
                data.pop(self.__entity_spec.primary_key[0])
            # also requires an expensive operation
            pk_field = self.__entity_spec.primary_key[0]
            increment = self.__get_autoincrement()
            collection.insert_one(
                data | {
                    pk_field: increment
                }
            )
            primary_key = {
                pk_field: increment
            }
        else:
            collection.update_one(primary_key, {'$set': data}, upsert=True)
        return primary_key

    def query(
        self,
        where: Optional[str] = None,
        params: Optional[DbParams] = None,
        orderby: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Generator[TEntity, None, None]:
        self.__deferred_init()
        if params is None:
            params = ()
        where_clause = where
        where_filter: dict[str, Any] = _parse_sql_where(where_clause, tuple(params)) if where_clause else {}
        raw_orderby = orderby
        sort_spec: list[tuple[str, int]] | None = None
        if raw_orderby is not None and len(raw_orderby) > 0:
            sort_entries = [s.strip() for s in raw_orderby.split(',')]
            sort_spec = []
            for entry in sort_entries:
                parts = entry.rsplit(None, 1)
                field = parts[0].strip().strip('`').strip('"')
                direction = parts[1].upper() if len(parts) > 1 else 'ASC'
                sort_spec.append((field, -1 if direction == 'DESC' else 1))
        collection = self._get_collection()
        cursor = collection.find(where_filter)
        if sort_spec:
            cursor = cursor.sort(sort_spec)
        if limit is not None and limit > 0:
            cursor = cursor.limit(limit)
        results = list(cursor)
        for result in results:
            doc = {k: v for k, v in result.items() if k != '_id'}
            yield hydrate(self.__entity_spec.entity_type, doc, from_bson=True)  # type: ignore[arg-type]


__all__ = ['MongoTableAdapter']
