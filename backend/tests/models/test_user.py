import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import User, Business
from app.test_db import engine, TestingSessionLocal, create_test_tables, drop_test_tables


@pytest.fixture(scope="function")
def test_db():
    create_test_tables()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        drop_test_tables()


class TestUser:
    def test_create_user(self, test_db: Session):
        # First create a business
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        # Then create a user
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            business_id=business.id
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"
        assert user.business_id == business.id
        assert user.created_at is not None

    def test_user_email_unique(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        user1 = User(
            email="test@example.com",
            password_hash="password1",
            business_id=business.id
        )
        test_db.add(user1)
        test_db.commit()
        
        with pytest.raises(IntegrityError):
            user2 = User(
                email="test@example.com",  # Same email
                password_hash="password2",
                business_id=business.id
            )
            test_db.add(user2)
            test_db.commit()

    def test_user_requires_business(self, test_db: Session):
        with pytest.raises(IntegrityError):
            user = User(
                email="test@example.com",
                password_hash="hashed_password",
                business_id=999  # Non-existent business
            )
            test_db.add(user)
            test_db.commit()

    def test_user_business_relationship(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            business_id=business.id
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.business.name == "Test Business"
        assert user.business.id == business.id

    def test_required_fields(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        # Test missing email
        with pytest.raises(IntegrityError):
            user = User(
                email=None,
                password_hash="hashed_password",
                business_id=business.id
            )
            test_db.add(user)
            test_db.commit()

        test_db.rollback()
        
        # Test missing password_hash
        with pytest.raises(IntegrityError):
            user = User(
                email="test@example.com",
                password_hash=None,
                business_id=business.id
            )
            test_db.add(user)
            test_db.commit()

        test_db.rollback()
        
        # Test missing business_id
        with pytest.raises(IntegrityError):
            user = User(
                email="test@example.com",
                password_hash="hashed_password",
                business_id=None
            )
            test_db.add(user)
            test_db.commit()

    def test_user_import_and_instantiation(self):
        """Test that User model can be imported and instantiated with minimal fields (no DB commit)"""
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            business_id=1
        )
        
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"
        assert user.business_id == 1
        assert user.__class__.__name__ == "User"