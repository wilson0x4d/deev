# BVT migration: seed initial users data

def apply(db_transaction):
    # Seed data is always inserted; first remove any placeholder rows left by migration 001.
    db_transaction.execute_nonquery("DELETE FROM users WHERE id = %?", ('__placeholder__',))
    db_transaction.execute_nonquery("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
    db_transaction.execute_nonquery("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
    db_transaction.commit()

def undo(db_transaction):
    # Delete all documents (use WHERE clause to ensure it parses correctly)
    db_transaction.execute_nonquery('DELETE FROM users WHERE 1=1')
    db_transaction.commit()
