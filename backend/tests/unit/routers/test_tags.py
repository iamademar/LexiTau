"""
Unit tests for tag management endpoints (clients, projects, categories).
Tests JWT protection and business scoping for all endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app import models
from app.auth import create_access_token, get_password_hash


@pytest.fixture
def test_business_and_user(db_session):
    """Create a test business and user"""
    # Create business
    business = models.Business(name="Test Business")
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    
    # Create user
    user = models.User(
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
        business_id=business.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return business, user


@pytest.fixture
def auth_headers(test_business_and_user):
    """Create authentication headers with JWT token"""
    _, user = test_business_and_user
    token = create_access_token(data={"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_business_and_user(db_session):
    """Create another business and user for testing isolation"""
    # Create another business
    other_business = models.Business(name="Other Business")
    db_session.add(other_business)
    db_session.commit()
    db_session.refresh(other_business)
    
    # Create user for other business
    other_user = models.User(
        email="other@example.com",
        password_hash=get_password_hash("otherpass123"),
        business_id=other_business.id
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    
    return other_business, other_user


class TestClientEndpoints:
    """Test client CRUD endpoints"""

    def test_create_client_success(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test successful client creation"""
        business, user = test_business_and_user
        
        client_data = {"name": "ACME Corp"}
        response = client.post("/clients", json=client_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "ACME Corp"
        assert data["business_id"] == business.id
        assert "id" in data
        assert "created_at" in data
        
        # Verify in database
        db_client = db_session.query(models.Client).filter_by(name="ACME Corp").first()
        assert db_client is not None
        assert db_client.business_id == business.id

    def test_create_client_duplicate_name_same_business_fails(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test creating client with duplicate name in same business fails"""
        business, user = test_business_and_user
        
        # Create first client
        client_data = {"name": "ACME Corp"}
        response = client.post("/clients", json=client_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Try to create duplicate
        response = client.post("/clients", json=client_data, headers=auth_headers)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_client_duplicate_name_different_business_succeeds(self, client: TestClient, db_session, test_business_and_user, other_business_and_user, auth_headers):
        """Test creating client with same name in different business succeeds"""
        business, user = test_business_and_user
        other_business, other_user = other_business_and_user
        
        # Create client in first business
        client_data = {"name": "ACME Corp"}
        response = client.post("/clients", json=client_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Create client with same name in other business
        other_token = create_access_token(data={"sub": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        response = client.post("/clients", json=client_data, headers=other_headers)
        assert response.status_code == 200
        
        # Verify both clients exist
        clients = db_session.query(models.Client).filter_by(name="ACME Corp").all()
        assert len(clients) == 2
        business_ids = [c.business_id for c in clients]
        assert business.id in business_ids
        assert other_business.id in business_ids


    def test_create_client_unauthorized(self, client: TestClient):
        """Test creating client without authentication fails"""
        client_data = {"name": "Test Client"}
        response = client.post("/clients", json=client_data)
        
        assert response.status_code in [401, 403]

    def test_list_clients_success(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test listing clients for business"""
        business, user = test_business_and_user
        
        # Create test clients
        client1 = models.Client(name="Client A", business_id=business.id)
        client2 = models.Client(name="Client B", business_id=business.id)
        db_session.add_all([client1, client2])
        db_session.commit()
        
        response = client.get("/clients", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        names = [c["name"] for c in data]
        assert "Client A" in names
        assert "Client B" in names
        
        # Verify all clients belong to the same business
        for client_data in data:
            assert client_data["business_id"] == business.id

    def test_list_clients_business_isolation(self, client: TestClient, db_session, test_business_and_user, other_business_and_user, auth_headers):
        """Test clients are isolated by business"""
        business, user = test_business_and_user
        other_business, other_user = other_business_and_user
        
        # Create clients for both businesses
        client1 = models.Client(name="Business 1 Client", business_id=business.id)
        client2 = models.Client(name="Business 2 Client", business_id=other_business.id)
        db_session.add_all([client1, client2])
        db_session.commit()
        
        # Test first business user only sees their clients
        response = client.get("/clients", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["name"] == "Business 1 Client"
        assert data[0]["business_id"] == business.id
        
        # Test other business user only sees their clients
        other_token = create_access_token(data={"sub": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        response = client.get("/clients", headers=other_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["name"] == "Business 2 Client"
        assert data[0]["business_id"] == other_business.id


    def test_list_clients_ordered_by_name(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test clients are returned ordered by name"""
        business, user = test_business_and_user
        
        # Create clients in non-alphabetical order
        client_z = models.Client(name="Z Corp", business_id=business.id)
        client_a = models.Client(name="A Corp", business_id=business.id)
        client_m = models.Client(name="M Corp", business_id=business.id)
        db_session.add_all([client_z, client_a, client_m])
        db_session.commit()
        
        response = client.get("/clients", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        names = [c["name"] for c in data]
        assert names == ["A Corp", "M Corp", "Z Corp"]


class TestProjectEndpoints:
    """Test project CRUD endpoints"""

    def test_create_project_success(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test successful project creation"""
        business, user = test_business_and_user
        
        project_data = {"name": "Website Redesign"}
        response = client.post("/projects", json=project_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Website Redesign"
        assert data["business_id"] == business.id
        assert "id" in data
        assert "created_at" in data
        
        # Verify in database
        db_project = db_session.query(models.Project).filter_by(name="Website Redesign").first()
        assert db_project is not None
        assert db_project.business_id == business.id

    def test_create_project_duplicate_name_same_business_fails(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test creating project with duplicate name in same business fails"""
        business, user = test_business_and_user
        
        # Create first project
        project_data = {"name": "Website Redesign"}
        response = client.post("/projects", json=project_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Try to create duplicate
        response = client.post("/projects", json=project_data, headers=auth_headers)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_project_duplicate_name_different_business_succeeds(self, client: TestClient, db_session, test_business_and_user, other_business_and_user, auth_headers):
        """Test creating project with same name in different business succeeds"""
        business, user = test_business_and_user
        other_business, other_user = other_business_and_user
        
        # Create project in first business
        project_data = {"name": "Website Redesign"}
        response = client.post("/projects", json=project_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Create project with same name in other business
        other_token = create_access_token(data={"sub": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        response = client.post("/projects", json=project_data, headers=other_headers)
        assert response.status_code == 200
        
        # Verify both projects exist
        projects = db_session.query(models.Project).filter_by(name="Website Redesign").all()
        assert len(projects) == 2
        business_ids = [p.business_id for p in projects]
        assert business.id in business_ids
        assert other_business.id in business_ids


    def test_list_projects_success(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test listing projects for business"""
        business, user = test_business_and_user
        
        # Create test projects
        project1 = models.Project(name="Project A", business_id=business.id)
        project2 = models.Project(name="Project B", business_id=business.id)
        db_session.add_all([project1, project2])
        db_session.commit()
        
        response = client.get("/projects", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        names = [p["name"] for p in data]
        assert "Project A" in names
        assert "Project B" in names
        
        # Verify all projects belong to the same business
        for project_data in data:
            assert project_data["business_id"] == business.id

    def test_list_projects_business_isolation(self, client: TestClient, db_session, test_business_and_user, other_business_and_user, auth_headers):
        """Test projects are isolated by business"""
        business, user = test_business_and_user
        other_business, other_user = other_business_and_user
        
        # Create projects for both businesses
        project1 = models.Project(name="Business 1 Project", business_id=business.id)
        project2 = models.Project(name="Business 2 Project", business_id=other_business.id)
        db_session.add_all([project1, project2])
        db_session.commit()
        
        # Test first business user only sees their projects
        response = client.get("/projects", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["name"] == "Business 1 Project"
        assert data[0]["business_id"] == business.id
        
        # Test other business user only sees their projects
        other_token = create_access_token(data={"sub": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        response = client.get("/projects", headers=other_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["name"] == "Business 2 Project"
        assert data[0]["business_id"] == other_business.id


class TestCategoryEndpoints:
    """Test category endpoints"""

    def test_list_categories_success(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test listing categories"""
        business, user = test_business_and_user
        
        # Create test categories (categories are global)
        category1 = models.Category(name="Office Supplies")
        category2 = models.Category(name="Software")
        category3 = models.Category(name="Travel")
        db_session.add_all([category1, category2, category3])
        db_session.commit()
        
        response = client.get("/categories", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 3
        names = [c["name"] for c in data]
        assert "Office Supplies" in names
        assert "Software" in names
        assert "Travel" in names
        
        # Verify structure
        for category in data:
            assert "id" in category
            assert "name" in category
            assert "created_at" in category

    def test_list_categories_ordered_by_name(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test categories are returned ordered by name"""
        business, user = test_business_and_user
        
        # Create categories in non-alphabetical order
        category_z = models.Category(name="Z Category")
        category_a = models.Category(name="A Category")
        category_m = models.Category(name="M Category")
        db_session.add_all([category_z, category_a, category_m])
        db_session.commit()
        
        response = client.get("/categories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        names = [c["name"] for c in data]
        assert names == ["A Category", "M Category", "Z Category"]

    def test_list_categories_global_access(self, client: TestClient, db_session, test_business_and_user, other_business_and_user, auth_headers):
        """Test categories are global and visible to all authenticated users"""
        business, user = test_business_and_user
        other_business, other_user = other_business_and_user
        
        # Create categories
        category1 = models.Category(name="Shared Category 1")
        category2 = models.Category(name="Shared Category 2")
        db_session.add_all([category1, category2])
        db_session.commit()
        
        # Test first business user can see categories
        response = client.get("/categories", headers=auth_headers)
        assert response.status_code == 200
        data1 = response.json()
        
        # Test other business user sees same categories
        other_token = create_access_token(data={"sub": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        response = client.get("/categories", headers=other_headers)
        assert response.status_code == 200
        data2 = response.json()
        
        # Both users should see the same categories
        assert len(data1) == len(data2) == 2
        names1 = {c["name"] for c in data1}
        names2 = {c["name"] for c in data2}
        assert names1 == names2
        assert "Shared Category 1" in names1
        assert "Shared Category 2" in names1

    def test_list_categories_unauthorized(self, client: TestClient):
        """Test listing categories without authentication fails"""
        response = client.get("/categories")
        assert response.status_code in [401, 403]


class TestAuthenticationAndAuthorization:
    """Test authentication and authorization for all endpoints"""

    def test_all_endpoints_require_authentication(self, client: TestClient):
        """Test all tag endpoints require authentication"""
        endpoints_and_methods = [
            ("POST", "/clients", {"name": "Test Client"}),
            ("GET", "/clients", None),
            ("POST", "/projects", {"name": "Test Project"}),
            ("GET", "/projects", None),
            ("GET", "/categories", None),
        ]
        
        for method, endpoint, data in endpoints_and_methods:
            if method == "POST":
                response = client.post(endpoint, json=data)
            else:
                response = client.get(endpoint)
            
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should require auth"

    def test_invalid_token_rejected(self, client: TestClient):
        """Test invalid JWT tokens are rejected"""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        
        endpoints_and_methods = [
            ("POST", "/clients", {"name": "Test Client"}),
            ("GET", "/clients", None),
            ("POST", "/projects", {"name": "Test Project"}),
            ("GET", "/projects", None),
            ("GET", "/categories", None),
        ]
        
        for method, endpoint, data in endpoints_and_methods:
            if method == "POST":
                response = client.post(endpoint, json=data, headers=invalid_headers)
            else:
                response = client.get(endpoint, headers=invalid_headers)
            
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should reject invalid token"

    def test_malformed_authorization_header_rejected(self, client: TestClient):
        """Test malformed authorization headers are rejected"""
        malformed_headers = {"Authorization": "InvalidFormat"}
        
        response = client.get("/clients", headers=malformed_headers)
        assert response.status_code in [401, 403, 422]  # 422 for validation error is also acceptable