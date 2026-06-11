# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import glob
import importlib
import importlib.util
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from .._MigrationData import _MigrationData, _MigrationData2
from .ConnectionString import ConnectionString
from .DbError import DbError
from .DbTableAdapter import DbTableAdapter


class DbMigrator:
    """
    Performs database changes from a set of "migration scripts."

    Migration scripts are scanned from a filesystem directory.
    """

    __connectionstring: ConnectionString
    __logger: logging.Logger
    __migrationdata_t: type

    def __init__(self, connectionstring: ConnectionString):
        self.__connectionstring = connectionstring
        self.__logger = logging.getLogger(__name__)
        match connectionstring.provider:
            case 'mongodb' | 'pymongo':
                self.__migrationdata_t = _MigrationData2
                # NOTE: because mongodb can't authorize administrative commands from a database OTHER than `admin`
                connectionstring.database = f'{connectionstring.database}?authSource=admin'
            case _:
                self.__migrationdata_t = _MigrationData

    def __get_or_create_migrations_table(self) -> DbTableAdapter[Any]:
        from ..utils import connect, create_table_adapter
        connection = connect(self.__connectionstring)
        table_adapter = create_table_adapter(self.__migrationdata_t, connection)
        table_adapter.create_table()
        return table_adapter

    def __load_migration(self, path: str) -> ModuleType:
        """Load a Python file as a module given its absolute file path."""
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError(f'Cannot create spec for {path}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        return module

    def apply(self, migrations_path: Path | str, stop_at: Optional[str] = None) -> None:
        from ..utils import begin_transaction, create_database
        create_database(self.__connectionstring)
        if isinstance(migrations_path, str):
            migrations_path = Path(migrations_path)
        if not os.path.exists(migrations_path):
            self.__logger.warning(f'Migrations path does not exist: {migrations_path}')
            return
        available_migrations = sorted(glob.glob(os.path.join(migrations_path, '*.py')))
        if len(available_migrations) == 0:
            self.__logger.warning(f'Migrations path does not contain migrations: {migrations_path}')
            return
        migrations_table = self.__get_or_create_migrations_table()
        applied_migrations = dict[str, int]({
            e.migration: e.id
            for e in migrations_table.query(orderby='migration')
        })
        skipped_migration_count = 0
        applied_migration_count = 0
        for migration_filepath in available_migrations:
            migration_name = os.path.splitext(os.path.basename(migration_filepath))[0]
            if migration_name not in applied_migrations:
                self.__logger.info(f'..apply migration "{migration_name}"')
                migration_module = self.__load_migration(migration_filepath)
                migration_func = getattr(migration_module, 'apply', None)
                if migration_func is not None:
                    with begin_transaction(self.__connectionstring) as db_transaction:
                        migration_func(db_transaction)
                    migrations_table.create(self.__migrationdata_t(migration=migration_name))  # type: ignore[call-arg]
                    migrations_table.commit()
                    applied_migration_count += 1
                else:
                    raise DbError(f'Invalid migration "{migration_name}", missing `apply(...)` call.')
            else:
                self.__logger.info(f'..skipped migration "{migration_name}" (already applied.)')
                skipped_migration_count += 1
            if stop_at is not None and migration_name == stop_at:
                self.__logger.info(f'..stopping at "{migration_name}", as instructed.')
                break
        self.__logger.info(f'Migrations applied {applied_migration_count}, skipped {skipped_migration_count}, available {len(available_migrations)}.')

    def undo(self, migrations_path: Path | str, stop_at: Optional[str] = None) -> None:
        from ..utils import begin_transaction, create_database
        create_database(self.__connectionstring)
        if isinstance(migrations_path, str):
            migrations_path = Path(migrations_path)
        if not os.path.exists(migrations_path):
            self.__logger.warning(f'Migrations path does not exist: {migrations_path}')
            return
        available_migrations = sorted(glob.glob(os.path.join(migrations_path, '*.py')), reverse=True)
        if len(available_migrations) == 0:
            self.__logger.warning(f'Migrations path does not contain migrations: {migrations_path}')
            return
        migrations_table = self.__get_or_create_migrations_table()
        applied_migrations = dict[str, int]({
            e.migration: e.id
            for e in migrations_table.query(orderby='migration DESC')
        })
        skipped_migration_count = 0
        applied_migration_count = 0
        for migration_filepath in available_migrations:
            migration_name = os.path.splitext(os.path.basename(migration_filepath))[0]
            if migration_name in applied_migrations:
                self.__logger.info(f'..undo migration "{migration_name}"')
                migration_module = self.__load_migration(migration_filepath)
                migration_func = getattr(migration_module, 'undo', None)
                if migration_func is not None:
                    with begin_transaction(self.__connectionstring) as db_transaction:
                        migration_func(db_transaction)
                    migrations_table.delete(id=applied_migrations.get(migration_name, 0))
                    migrations_table.commit()
                    applied_migration_count += 1
                else:
                    raise DbError(f'Invalid migration "{migration_name}", missing `undo(...)` call.')
            else:
                self.__logger.info(f'..skipped migration "{migration_name}" (not applied.)')
                skipped_migration_count += 1
            if stop_at is not None and migration_name == stop_at:
                self.__logger.info(f'..stopping at "{migration_name}", as instructed.')
                break
        self.__logger.info(f'Migrations undone {applied_migration_count}, skipped {skipped_migration_count}, available {len(available_migrations)}.')


__all__ = ['DbMigrator']
