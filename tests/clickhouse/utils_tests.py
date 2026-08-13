# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database
from uuid import uuid4
from punit import fact, trait

@fact
@trait('integration')
@trait('clickhouse')
def cannot_connect_when_nonexistent_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    cxnstring.database = uuid4().hex
    try:
        with connect(cxnstring) as connection:
            connection.close()
    except Exception:
        pass
    else:
        assert False, f'expected failure for non-existent database: {cxnstring.database}'

@fact
@trait('integration')
@trait('clickhouse')
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.clickhouse_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    try:
        with connect(cxnstring) as connection:
            connection.close()
    finally:
        try:
            with connect(cxnstring) as connection:
                connection.cursor().execute(f'DROP DATABASE IF EXISTS `{cxnstring.database}`')
        except Exception:
            pass
