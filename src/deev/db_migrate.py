# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
import argparse
from datetime import datetime
import hanaro
import platform
import sys

from .common.connection_string import ConnectionString
from .utils import apply_migrations, generate_entity_ddl, undo_migrations


def __parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and parse the command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='db-migrate',
        description='Utility for applying, undoing, or generating migrations.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging.',
    )

    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        metavar='<COMMAND>',
        help='Action to perform.',
    )

    apply_parser = subparsers.add_parser(
        'apply',
        help='Apply migrations.',
    )
    apply_parser.add_argument(
        'migration_name',
        metavar='migration-name',
        help='The name of the migration at which apply should stop processing.  Specify "all" to process all migrations.',
    )
    apply_parser.add_argument(
        'connection',
        metavar='connection',
        help='Database connection string (name from config or literal `key=value` format).',
    )
    apply_parser.add_argument(
        'path',
        nargs='?',
        default=None,
        metavar='path',
        help='Directory containing migration scripts (optional). If omitted, a path is calculated from the connection argument, ie. `./migrations/database_name/`.',
    )

    undo_parser = subparsers.add_parser(
        'undo',
        help='Undo migrations.',
    )
    undo_parser.add_argument(
        'migration_name',
        metavar='migration-name',
        help='The name of the migration at which undo should stop processing.  Specify "all" to process all migrations.',
    )
    undo_parser.add_argument(
        'connection',
        metavar='connection',
        help='Database connection string (name from config or literal `key=value` format).',
    )
    undo_parser.add_argument(
        'path',
        nargs='?',
        default=None,
        metavar='path',
        help='Directory containing migration scripts (optional). If omitted, a path is calculated from the connection argument, ie. `./migrations/database_name/`.',
    )

    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate DDL.',
    )
    generate_parser.add_argument(
        'type',
        metavar='type',
        choices=['entity', 'database'],
        help='The type of object to generate DDL for (entity or database).',
    )
    generate_parser.add_argument(
        'fqn',
        metavar='fqn',
        help='The fully-qualified type name, ie. `my_project.my_entities.my_entity.MyEntity`.',
    )
    generate_parser.add_argument(
        'connection',
        metavar='connection',
        help='Database connection string (name from config or literal `key=value` format).',
    )

    return parser.parse_args(argv)


def main() -> None:
    configuration = appsettings2.get_configuration()
    if not configuration.has_key('logging'):
        configuration['logging'] = {
            'level': 'DEBUG' if '--verbose' in sys.argv else 'INFO',
            'format': '%(message)s',
            'handlers': [
                {
                    'type': 'console',
                    'level': 'DEBUG'
                }
            ],
        }
    hanaro.configure_logging(configuration)
    try:
        args = __parse_args()
        connection: ConnectionString
        if '=' not in args.connection:
            # load via appsettings2
            candidate_config_keys = list[str]([
                f'connectionStrings__{args.connection}',
                f'connections__{args.connection}'
            ])
            for candidate_config_key in candidate_config_keys:
                candidate_connection_str = configuration.get(candidate_config_key, None)
                if candidate_connection_str is not None:
                    connection = ConnectionString(candidate_connection_str)
                    break
            assert connection is not None  # type: ignore[unbound-name]
        else:
            # take as literal
            connection = ConnectionString(args.connection)

        match args.command:
            case 'apply':
                apply_migrations(args.migration_name, connection, args.path)
            case 'undo':
                undo_migrations(args.migration_name, connection, args.path)
            case 'generate':
                ddl: list[str]
                match args.type:
                    case 'entity':
                        from deev.utils import generate_entity_ddl
                        ddl = generate_entity_ddl(connection, args.fqn)
                    case 'database':
                        from deev.utils import generate_dbadapter_ddl
                        ddl = generate_dbadapter_ddl(connection, args.fqn)
                ddl_ident = f'-- Generated {datetime.now()} on {platform.node()} --'
                ddl_sep = '-' * len(ddl_ident)
                print(f'{ddl_sep}\n{ddl_ident}\n{ddl_sep}\n')
                print(f'USE {connection.database};\n')
                for stmt in ddl:
                    print(f'{stmt};\n')
                if connection.provider == 'clickhouse' and connection.parameters.get('engine', 'Replicate').startswith('Replicate'):
                    print(f'SYSTEM SYNC DATABASE REPLICA {connection.database};\n')
    except Exception as ex:
        hanaro.get_logger().exception(ex)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
