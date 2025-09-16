from sqlalchemy.types import TypeDecorator, JSON as SAJSON
from sqlalchemy.dialects.postgresql import JSONB

class JSONBCompat(TypeDecorator):
    """
    Uses PostgreSQL JSONB when available; falls back to generic JSON on other DBs (e.g., SQLite).
    Safe for CREATE TABLE in tests that bind to SQLite.
    """
    impl = SAJSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(SAJSON())