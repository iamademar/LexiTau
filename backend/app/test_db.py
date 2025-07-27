from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from .db import Base

# Use PostgreSQL test database
POSTGRES_TEST_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:password@postgres_test:5432/lexitau_test")

engine = create_engine(POSTGRES_TEST_URL)
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