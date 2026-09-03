# BVT migration: create the users collection (collection is implicitly created on first insert)

def apply(db_transaction):
    # In MongoDB, collection is created implicitly via execute_nonquery insert
    db_transaction.execute_nonquery("INSERT INTO users (id, name) VALUES ('__placeholder__', 'placeholder')")
    db_transaction.commit()

def undo(db_transaction):
    # Undo clears everything since migration 001 implicitly creates the collection
    db_transaction.execute_nonquery('DELETE FROM users')
    db_transaction.commit()
