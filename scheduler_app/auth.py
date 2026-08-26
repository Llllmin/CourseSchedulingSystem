"""Authentication helper functions.

The project stores hashed passwords instead of plain-text passwords. This is
simple enough for an IA prototype while still showing an important security
idea: the database should not contain readable passwords.
"""

import hashlib


def hash_password(password: str) -> str:
    """Convert a password into a stable SHA-256 hash for database comparison."""
    # encode() changes the string into bytes because hashlib works on bytes.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
