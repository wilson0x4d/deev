# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT


def apply(db):
    db.commit()


def undo(db):
    db.commit()
