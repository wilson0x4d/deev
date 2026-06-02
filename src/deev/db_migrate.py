# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
import argparse
import hanaro
import sys

from .common.ConnectionString import ConnectionString
from .utils import apply_migrations, undo_migrations


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
        'connectionstring',
        metavar='connectionstring',
        help='Database connection string.',
    )
    apply_parser.add_argument(
        'path',
        nargs='?',
        default=None,
        metavar='path',
        help='Directory containing migration scripts (optional). If omitted, a path is calculated from the connectionstring argument, ie. `./migrations/databnase_name/`.',
    )
    apply_parser.add_argument(
        '--stop-at',
        dest='stop_at',
        metavar='name',
        help='Stop processing at the named migration.',
    )

    undo_parser = subparsers.add_parser(
        'undo',
        help='Undo migrations.',
    )
    undo_parser.add_argument(
        'connectionstring',
        metavar='connectionstring',
        help='Database connection string.',
    )
    undo_parser.add_argument(
        'path',
        nargs='?',
        default=None,
        metavar='path',
        help='Directory containing migration scripts (optional). If omitted, a path is calculated from the connectionstring argument, ie. `./migrations/databnase_name/`.',
    )
    undo_parser.add_argument(
        '--stop-at',
        dest='stop_at',
        metavar='name',
        help='Stop processing at the named migration.',
    )

    # # # generate_parser = subparsers.add_parser(
    # # #     'generate',
    # # #     help='Generate a new migration script.',
    # # # )
    # # # generate_parser.add_argument(
    # # #     'path',
    # # #     metavar='path',
    # # #     help='Directory where the new migration will be created.',
    # # # )
    # # # generate_parser.add_argument(
    # # #     'name',
    # # #     metavar='name',
    # # #     help='Name of the new migration.',
    # # # )
    # # # generate_parser.add_argument(
    # # #     'connectionstring',
    # # #     metavar='connectionstring',
    # # #     help='Database connection string.',
    # # # )
    # # # generate_parser.add_argument(
    # # #     'path',
    # # #     nargs='?',
    # # #     default=None,
    # # #     metavar='path',
    # # #     help='Directory containing migration scripts (optional). If omitted, a path is calculated from the connectionstring argument, ie. `./migrations/databnase_name/`.',
    # # # )

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

    args = __parse_args()
    connectionstring: ConnectionString
    if '=' not in args.connectionstring:
        # load via appsettings2
        candidate_config_keys = list[str]([
            f'connectionStrings__{args.connectionstring}',
            f'connections__{args.connectionstring}'
        ])
        for candidate_config_key in candidate_config_keys:
            candidate_connection_str = configuration.get(candidate_config_key, None)
            if candidate_connection_str is not None:
                connectionstring = ConnectionString(candidate_connection_str)
                break
        assert connectionstring is not None  # type: ignore[unbound-name]
    else:
        # take as literal
        connectionstring = ConnectionString(args.connectionstring)

    match args.command:
        case 'apply':
            apply_migrations(connectionstring, args.path, getattr(args, 'stop_at', None))
        case 'undo':
            undo_migrations(connectionstring, args.path, getattr(args, 'stop_at', None))
