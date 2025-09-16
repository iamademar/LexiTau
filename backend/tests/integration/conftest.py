# backend/tests/integration/conftest.py
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db

DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:password@postgres_test:5432/lexitau_test",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@pytest.fixture(scope="session", autouse=True)
def _enable_vector_extension():
    """Enable pgvector extension before creating schema"""
    with engine.connect() as conn:
        # Enable vector extension if not already enabled
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
        conn.commit()
    yield

@pytest.fixture(scope="session", autouse=True)
def _create_schema_once(_enable_vector_extension):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def connection():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()

@pytest.fixture
def db_session(connection):
    s = TestingSessionLocal(bind=connection)
    try:
        yield s
    finally:
        s.close()

@pytest.fixture(autouse=True)
def _override_get_db(db_session):
    def _get_db():
        yield db_session
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    return TestClient(app)