# BVT migration: create the users table

def apply(db_transaction):
    db_transaction.execute_nonquery(
        'CREATE TABLE IF NOT EXISTS users (id Int64, name String NOT NULL) ENGINE = MergeTree() ORDER BY (id)'
    )
    db_transaction.commit()

def undo(db_transaction):
    db_transaction.execute_nonquery('DROP TABLE IF EXISTS users')
    db_transaction.commit()
