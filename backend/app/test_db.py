from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from .db import Base

SQLITE_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLITE_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Enable foreign key constraints for SQLite
def _fk_pragma_on_connect(dbapi_con, con_record):
    dbapi_con.execute('pragma foreign_keys=ON')

event.listen(engine, 'connect', _fk_pragma_on_connect)
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