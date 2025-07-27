import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models import User, Business
from app.test_db import engine, TestingSessionLocal, create_test_tables, drop_test_tables
from app.db import get_db
from app.auth import get_password_hash, verify_password, verify_token

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def test_db():
    create_test_tables()
    app.dependency_overrides[get_db] = override_get_db
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        drop_test_tables()
        # Clean up the override
        app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def client():
    return TestClient(app)

class TestSignup:
    def test_successful_signup(self, test_db: Session, client):
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "testpassword123",
                "business_name": "Test Business"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "user" in data
        assert "business" in data
        assert "access_token" in data
        assert "token_type" in data
        
        # Check user data
        assert data["user"]["email"] == "test@example.com"
        assert "id" in data["user"]
        assert "business_id" in data["user"]
        assert "created_at" in data["user"]
        
        # Check business data
        assert data["business"]["name"] == "Test Business"
        assert "id" in data["business"]
        assert "created_at" in data["business"]
        
        # Check token
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        
        # Verify token is valid
        payload = verify_token(data["access_token"])
        assert payload is not None
        assert payload["sub"] == "test@example.com"
        assert "user_id" in payload
        assert "business_id" in payload
        
        # Verify data in database
        user = test_db.query(User).filter(User.email == "test@example.com").first()
        assert user is not None
        assert user.business.name == "Test Business"
        assert verify_password("testpassword123", user.password_hash)

    def test_duplicate_email_signup(self, test_db: Session, client):
        # First signup
        client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "password1",
                "business_name": "Business 1"
            }
        )
        
        # Second signup with same email
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "password2",
                "business_name": "Business 2"
            }
        )
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_invalid_email_signup(self, test_db: Session, client):
        response = client.post(
            "/auth/signup",
            json={
                "email": "invalid-email",
                "password": "testpassword123",
                "business_name": "Test Business"
            }
        )
        
        assert response.status_code == 422  # Validation error

    def test_missing_fields_signup(self, test_db: Session, client):
        # Missing password
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "business_name": "Test Business"
            }
        )
        assert response.status_code == 422
        
        # Missing business_name
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "testpassword123"
            }
        )
        assert response.status_code == 422
        
        # Missing email
        response = client.post(
            "/auth/signup",
            json={
                "password": "testpassword123",
                "business_name": "Test Business"
            }
        )
        assert response.status_code == 422

class TestLogin:
    def test_successful_login(self, test_db: Session, client):
        # First create a user
        signup_response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "testpassword123",
                "business_name": "Test Business"
            }
        )
        assert signup_response.status_code == 200
        
        # Now login
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123"
            }
        )
        
        assert login_response.status_code == 200
        data = login_response.json()
        
        # Check response structure
        assert "user" in data
        assert "access_token" in data
        assert "token_type" in data
        
        # Check user data
        assert data["user"]["email"] == "test@example.com"
        assert "id" in data["user"]
        assert "business_id" in data["user"]
        
        # Check token
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        
        # Verify token is valid
        payload = verify_token(data["access_token"])
        assert payload is not None
        assert payload["sub"] == "test@example.com"

    def test_invalid_email_login(self, test_db: Session, client):
        response = client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "testpassword123"
            }
        )
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_invalid_password_login(self, test_db: Session, client):
        # Create a user
        client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "correctpassword",
                "business_name": "Test Business"
            }
        )
        
        # Try login with wrong password
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_missing_credentials_login(self, test_db: Session, client):
        # Missing password
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com"
            }
        )
        assert response.status_code == 422
        
        # Missing email
        response = client.post(
            "/auth/login",
            json={
                "password": "testpassword123"
            }
        )
        assert response.status_code == 422

class TestAuthFlow:
    def test_complete_auth_flow(self, test_db: Session, client):
        # 1. Signup
        signup_response = client.post(
            "/auth/signup",
            json={
                "email": "complete@example.com",
                "password": "testpassword123",
                "business_name": "Complete Test Business"
            }
        )
        assert signup_response.status_code == 200
        signup_data = signup_response.json()
        
        # 2. Login
        login_response = client.post(
            "/auth/login",
            json={
                "email": "complete@example.com",
                "password": "testpassword123"
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        
        # 3. Verify both tokens work and return same user
        assert signup_data["user"]["id"] == login_data["user"]["id"]
        assert signup_data["user"]["email"] == login_data["user"]["email"]
        assert signup_data["user"]["business_id"] == login_data["user"]["business_id"]
        
        # 4. Test authenticated endpoint with token
        token = login_data["access_token"]
        me_response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == "complete@example.com"

    def test_protected_endpoint_without_token(self, test_db: Session, client):
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self, test_db: Session, client):
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

class TestPasswordHashing:
    def test_password_hashing(self):
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original
        assert hashed != password
        
        # Should be able to verify
        assert verify_password(password, hashed)
        
        # Wrong password should not verify
        assert not verify_password("wrongpassword", hashed)
        
        # Same password should generate different hashes
        hashed2 = get_password_hash(password)
        assert hashed != hashed2
        assert verify_password(password, hashed2)