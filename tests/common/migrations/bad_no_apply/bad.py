# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT


def undo(db_transaction):
    db_transaction.commit()
