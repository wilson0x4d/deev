# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.common import DbError
from punit import fact


@fact
def basic_verification() -> None:
    try:
        raise DbError(f'big oop!')
    except DbError as dberr:
        assert str(dberr) == 'DbError(reason=\'big oop!\')', f'expected "DbError(reason=\'big oop!\')", got "{str(dberr)}"'
        assert str(dberr) == dberr.__repr__(), f'expected "{str(dberr)}", got "{dberr.__repr__()}"'
