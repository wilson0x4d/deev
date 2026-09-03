# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database, drop_database
from punit import fact, trait
from uuid import uuid4



@fact
@trait('integration')
@trait('sqlite3')
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connections.sqlite_test)
    cxnstring.database = f'deev_test_{uuid4().hex}.db'
    create_database(cxnstring)
    drop_database(cxnstring)
