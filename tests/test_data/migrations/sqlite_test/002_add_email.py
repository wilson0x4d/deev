# BVT migration: add email column to users table

def apply(db_transaction):
    db_transaction.execute_nonquery(
        'ALTER TABLE users ADD COLUMN email TEXT(256)'
    )
    db_transaction.commit()

def undo(db_transaction):
    # SQLite < 3.35 does not support DROP COLUMN, so we recreate the table
    # For BVT purposes this is sufficient — the point is that undo runs without error
    db_transaction.execute_nonquery(
        'CREATE TABLE users_backup (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT(256) NOT NULL)'
    )
    db_transaction.execute_nonquery('INSERT INTO users_backup (id, name) SELECT id, name FROM users')
    db_transaction.execute_nonquery('DROP TABLE users')
    db_transaction.execute_nonquery('ALTER TABLE users_backup RENAME TO users')
    db_transaction.commit()

