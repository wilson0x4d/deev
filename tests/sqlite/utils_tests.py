# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database
import os
from punit import fact, trait
import shutil
from uuid import uuid4


@fact
@trait('integration')
@trait('sqlite3')
def cannot_connect_when_nonexistent_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    try:
        with connect(cxnstring) as connection:
            connection.close()
    except Exception:
        pass
    else:
        assert False, f'expected failure for non-existent database: {cxnstring.database}'


@fact
@trait('integration')
@trait('sqlite3')
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    database_path = os.path.dirname(cxnstring.database if cxnstring.server is None else os.path.join(cxnstring.server, cxnstring.database))
    assert os.path.exists(database_path)
    shutil.rmtree(database_path)
    assert not os.path.exists(database_path)
