# BVT migration: create the users table

def apply(db_transaction):
    db_transaction.execute_nonquery(
        'CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTO_INCREMENT, name VARCHAR(256) NOT NULL)'
    )
    db_transaction.commit()

def undo(db_transaction):
    db_transaction.execute_nonquery('DROP TABLE IF EXISTS users')
    db_transaction.commit()
