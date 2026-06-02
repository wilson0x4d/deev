# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common import DbError
from punit import fact


@fact
def basic_verification() -> None:
    try:
        raise DbError('big oop!')
    except DbError as dberr:
        assert str(dberr) == 'big oop!', f'expected "big oop!", got "{str(dberr)}"'
        assert dberr.__repr__() == "DbError(reason='big oop!')", f'expected "DbError(\'big oop!\')", got "{dberr.__repr__()}"'
