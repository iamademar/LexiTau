import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Business, User, Document
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


class TestBusiness:
    def test_create_business(self, test_db: Session):
        business = Business(name="Test Business LLC")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        assert business.id is not None
        assert business.name == "Test Business LLC"
        assert business.created_at is not None

    def test_business_name_required(self, test_db: Session):
        with pytest.raises(IntegrityError):
            business = Business(name=None)
            test_db.add(business)
            test_db.commit()

    def test_business_users_relationship(self, test_db: Session):
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
        
        # Refresh business to load the relationship
        test_db.refresh(business)
        assert len(business.users) == 1
        assert business.users[0].email == "test@example.com"


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


class TestBusinessUserIntegration:
    def test_multiple_users_same_business(self, test_db: Session):
        business = Business(name="Multi-User Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        user1 = User(
            email="user1@example.com",
            password_hash="password1",
            business_id=business.id
        )
        user2 = User(
            email="user2@example.com",
            password_hash="password2",
            business_id=business.id
        )
        
        test_db.add_all([user1, user2])
        test_db.commit()
        test_db.refresh(business)
        
        assert len(business.users) == 2
        emails = [user.email for user in business.users]
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails

    def test_cascade_behavior(self, test_db: Session):
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
        
        # Verify both exist
        assert test_db.query(Business).count() == 1
        assert test_db.query(User).count() == 1
        
        # Delete business (this should not automatically delete users in the current setup)
        test_db.delete(business)
        
        # This should fail due to foreign key constraint
        with pytest.raises(IntegrityError):
            test_db.commit()