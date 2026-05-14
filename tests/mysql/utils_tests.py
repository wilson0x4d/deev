# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from datetime import datetime, timedelta, timezone
from deev import entity, field
from deev.common import ConnectionString
from deev.utils import connect, create_database
from deev.mysql.MysqlTableAdapter import MysqlTableAdapter
from uuid import UUID, uuid4
from punit import fact, trait
from typing import Any


@fact
@trait('integration')
def cannot_connect_when_nonexistent_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connectionStrings.mysql_test)
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
def can_create_database() -> None:
    appsettings = appsettings2.get_configuration()
    cxnstring = ConnectionString(appsettings.connectionStrings.mysql_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    with connect(cxnstring) as connection:
        cursor = connection.cursor()
        cursor.execute(f'DROP DATABASE {cxnstring.database};')
        connection.commit()
        connection.close()
