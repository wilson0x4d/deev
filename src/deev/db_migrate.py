# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

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
        'path',
        metavar='path',
        help='Directory containing migration scripts.',
    )
    apply_parser.add_argument(
        '--stop-at',
        dest='stop_at',
        metavar='name',
        help='Stop processing at the named migration.',
    )
    apply_parser.add_argument(
        'connectionstring',
        metavar='connectionstring',
        help='Database connection string.',
    )

    undo_parser = subparsers.add_parser(
        'undo',
        help='Undo migrations.',
    )
    undo_parser.add_argument(
        'path',
        metavar='path',
        help='Directory containing migration scripts.',
    )
    undo_parser.add_argument(
        '--stop-at',
        dest='stop_at',
        metavar='name',
        help='Stop processing at the named migration.',
    )
    undo_parser.add_argument(
        'connectionstring',
        metavar='connectionstring',
        help='Database connection string.',
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

    return parser.parse_args(argv)


def main() -> None:
    hanaro.configure_logging({
        'logging': {
            'level': 'DEBUG' if '--verbose' in sys.argv else 'INFO',
            'format': '%(message)s',
            'handlers': [
                {
                    'type': 'console',
                    'level': 'DEBUG'
                }
            ],
        }
    })
    args = __parse_args()
    match args.command:
        case 'apply':
            connectionstring = ConnectionString(args.connectionstring)
            apply_migrations(connectionstring, args.path, getattr(args, 'stop_at', None))
        case 'undo':
            connectionstring = ConnectionString(args.connectionstring)
            undo_migrations(connectionstring, args.path, getattr(args, 'stop_at', None))
