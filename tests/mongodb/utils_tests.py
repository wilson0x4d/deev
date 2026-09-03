# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
from deev.common import ConnectionString
from deev.utils import connect, create_database, drop_database
from uuid import uuid4
from punit import fact, trait


@fact
@trait('integration')
@trait('mongodb')
def can_create_and_drop_database() -> None:
    configuration = appsettings2.get_configuration()
    cxnstring = ConnectionString(configuration.connections.mongo_test)
    cxnstring.database = uuid4().hex
    create_database(cxnstring)
    drop_database(cxnstring)
