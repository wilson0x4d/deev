# BVT migration: add email field to users documents

def apply(db_transaction):
    # In MongoDB, this would be a findAndUpdate operation; here we use a no-op SQL statement
    db_transaction.execute_nonquery('SELECT 1')
    db_transaction.commit()

def undo(db_transaction):
    db_transaction.execute_nonquery('SELECT 1')
    db_transaction.commit()
