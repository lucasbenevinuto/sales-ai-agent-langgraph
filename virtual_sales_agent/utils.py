import sqlite3
from contextlib import contextmanager


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect("database/db/store.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
