from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from .db import Base

# Use PostgreSQL test database with explicit driver and connection settings
POSTGRES_TEST_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://postgres:password@postgres_test:5432/lexitau_test")

engine = create_engine(
    POSTGRES_TEST_URL,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_recycle=1800,
    connect_args={
        "connect_timeout": 10
    }
)
# Replace PostgreSQL configuration with SQLite
# SQLITE_DATABASE_URL = "sqlite:///./test.db"

# engine = create_engine(
#     SQLITE_DATABASE_URL,
#     connect_args={"check_same_thread": False}  # Required for SQLite
# )
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_test_tables():
    Base.metadata.create_all(bind=engine)

def drop_test_tables():
    Base.metadata.drop_all(bind=engine)