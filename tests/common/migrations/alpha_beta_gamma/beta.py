# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT


def apply(db_transaction):
    db_transaction.commit()


def undo(db_transaction):
    db_transaction.commit()
