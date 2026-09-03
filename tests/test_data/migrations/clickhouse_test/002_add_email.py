# BVT migration: add email column

def apply(db_transaction):
    db_transaction.execute_nonquery(
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS email String'
    )
    db_transaction.commit()

def undo(db_transaction):
    db_transaction.execute_nonquery('ALTER TABLE users DROP COLUMN IF EXISTS email')
    db_transaction.commit()
