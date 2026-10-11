"""Read-only collector database access with deterministic handle ownership."""
from contextlib import contextmanager
import sqlite3


@contextmanager
def readonly_database(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)
    try:
        connection.row_factory = sqlite3.Row
        yield connection
    finally:
        # sqlite3.Connection.__exit__ handles transactions, not connection close.
        connection.close()
