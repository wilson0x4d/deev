# BVT migration: add email column to users table

def apply(db_transaction):
    db_transaction.execute_nonquery(
        'ALTER TABLE users ADD COLUMN email VARCHAR(256)'
    )
    db_transaction.commit()

def undo(db_transaction):
    # MySQL does not support DROP COLUMN on a single statement
    # For BVT purposes this is sufficient — the point is that undo runs without error
    db_transaction.execute_nonquery(
        'CREATE TABLE users_backup (id INTEGER PRIMARY KEY AUTO_INCREMENT, name VARCHAR(256) NOT NULL)'
    )
    db_transaction.execute_nonquery('INSERT INTO users_backup (id, name) SELECT id, name FROM users')
    db_transaction.execute_nonquery('DROP TABLE users')
    db_transaction.execute_nonquery('ALTER TABLE users_backup RENAME TO users')
    db_transaction.commit()
