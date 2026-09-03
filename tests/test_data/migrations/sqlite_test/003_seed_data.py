# BVT migration: seed initial users data

def apply(db_transaction):
    db_transaction.execute_nonquery("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
    db_transaction.execute_nonquery("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
    db_transaction.commit()

def undo(db_transaction):
    db_transaction.execute_nonquery('DELETE FROM users')
    db_transaction.commit()
