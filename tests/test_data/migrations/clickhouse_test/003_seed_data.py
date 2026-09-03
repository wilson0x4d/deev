# BVT migration: seed data

def apply(db_transaction):
    db_transaction.execute_nonquery(
        "INSERT INTO users (id, name, email) VALUES (%?, %?, %?)",
        [1, 'Alice', 'alice@example.com']
    )
    db_transaction.execute_nonquery(
        "INSERT INTO users (id, name, email) VALUES (%?, %?, %?)",
        [2, 'Bob', 'bob@example.com']
    )
    db_transaction.commit()

def undo(db_transaction):
    db_transaction.execute_nonquery('ALTER TABLE users DELETE WHERE id = 1 OR id = 2')
    db_transaction.commit()
