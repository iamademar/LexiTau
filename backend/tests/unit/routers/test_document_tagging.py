"""
Unit tests for document tagging endpoint.
Tests valid and invalid tagging scenarios, including business scoping and edge cases.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime

from app.main import app
from app import models
from app.auth import create_access_token, get_password_hash
from app.enums import DocumentStatus, DocumentType, FileType, DocumentClassification


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


@pytest.fixture
def test_document(db_session, test_business_and_user):
    """Create a test document"""
    business, user = test_business_and_user
    
    document = models.Document(
        user_id=user.id,
        business_id=business.id,
        filename="test_invoice.pdf",
        file_url="https://example.com/test_invoice.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        classification=DocumentClassification.EXPENSE,
        status=DocumentStatus.COMPLETED
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    return document


@pytest.fixture
def test_client_project_category(db_session, test_business_and_user):
    """Create test client, project, and category"""
    business, user = test_business_and_user
    
    # Create client
    client = models.Client(name="Test Client", business_id=business.id)
    db_session.add(client)
    
    # Create project
    project = models.Project(name="Test Project", business_id=business.id)
    db_session.add(project)
    
    # Create category (global)
    category = models.Category(name="Office Supplies")
    db_session.add(category)
    
    db_session.commit()
    db_session.refresh(client)
    db_session.refresh(project)
    db_session.refresh(category)
    
    return client, project, category


class TestDocumentTaggingSuccess:
    """Test successful tagging scenarios"""
    
    def test_tag_document_with_all_tags(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test tagging document with client, project, and category"""
        test_client, test_project, test_category = test_client_project_category
        
        tag_data = {
            "client_id": test_client.id,
            "project_id": test_project.id,
            "category_id": test_category.id
        }
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Document tagged successfully"
        assert data["document_id"] == str(test_document.id)
        assert data["client_id"] == test_client.id
        assert data["project_id"] == test_project.id
        assert data["category_id"] == test_category.id
        assert "updated_at" in data
        
        # Verify in database
        db_session.refresh(test_document)
        assert test_document.client_id == test_client.id
        assert test_document.project_id == test_project.id
        assert test_document.category_id == test_category.id

    def test_tag_document_with_client_only(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test tagging document with only client"""
        test_client, _, _ = test_client_project_category
        
        tag_data = {
            "client_id": test_client.id,
            "project_id": None,
            "category_id": None
        }
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["client_id"] == test_client.id
        assert data["project_id"] is None
        assert data["category_id"] is None
        
        # Verify in database
        db_session.refresh(test_document)
        assert test_document.client_id == test_client.id
        assert test_document.project_id is None
        assert test_document.category_id is None

    def test_tag_document_remove_existing_tags(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test removing existing tags by setting to null"""
        test_client, test_project, test_category = test_client_project_category
        
        # First tag the document
        test_document.client_id = test_client.id
        test_document.project_id = test_project.id
        test_document.category_id = test_category.id
        db_session.commit()
        
        # Now remove all tags
        tag_data = {
            "client_id": None,
            "project_id": None,
            "category_id": None
        }
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["client_id"] is None
        assert data["project_id"] is None
        assert data["category_id"] is None
        
        # Verify in database
        db_session.refresh(test_document)
        assert test_document.client_id is None
        assert test_document.project_id is None
        assert test_document.category_id is None

    def test_tag_document_partial_update(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test updating only some tags while preserving others"""
        test_client, test_project, test_category = test_client_project_category
        
        # Set initial tags
        test_document.client_id = test_client.id
        test_document.project_id = test_project.id
        db_session.commit()
        
        # Update only category
        tag_data = {
            "category_id": test_category.id
        }
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should preserve existing client and project, add category
        assert data["client_id"] == test_client.id
        assert data["project_id"] == test_project.id
        assert data["category_id"] == test_category.id


class TestDocumentTaggingValidation:
    """Test validation and error scenarios"""

    def test_tag_nonexistent_document(self, client: TestClient, auth_headers):
        """Test tagging non-existent document"""
        fake_document_id = uuid4()
        tag_data = {"client_id": 1}
        
        response = client.put(f"/documents/{fake_document_id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 404
        assert "not found or access denied" in response.json()["detail"]

    def test_tag_document_wrong_business(self, client: TestClient, db_session, test_document, other_business_and_user):
        """Test tagging document from different business"""
        other_business, other_user = other_business_and_user
        
        # Create token for other user
        other_token = create_access_token(data={"sub": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        tag_data = {"client_id": 1}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=other_headers)
        
        assert response.status_code == 404
        assert "not found or access denied" in response.json()["detail"]

    def test_tag_with_nonexistent_client(self, client: TestClient, test_document, auth_headers):
        """Test tagging with non-existent client"""
        tag_data = {"client_id": 99999}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Client not found or access denied" in response.json()["detail"]

    def test_tag_with_nonexistent_project(self, client: TestClient, test_document, auth_headers):
        """Test tagging with non-existent project"""
        tag_data = {"project_id": 99999}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Project not found or access denied" in response.json()["detail"]

    def test_tag_with_nonexistent_category(self, client: TestClient, test_document, auth_headers):
        """Test tagging with non-existent category"""
        tag_data = {"category_id": 99999}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Category not found" in response.json()["detail"]

    def test_tag_with_foreign_business_client(self, client: TestClient, db_session, test_document, other_business_and_user, auth_headers):
        """Test tagging with client from different business"""
        other_business, other_user = other_business_and_user
        
        # Create client in other business
        other_client = models.Client(name="Other Client", business_id=other_business.id)
        db_session.add(other_client)
        db_session.commit()
        
        tag_data = {"client_id": other_client.id}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Client not found or access denied" in response.json()["detail"]
        assert "must belong to your business" in response.json()["detail"]

    def test_tag_with_foreign_business_project(self, client: TestClient, db_session, test_document, other_business_and_user, auth_headers):
        """Test tagging with project from different business"""
        other_business, other_user = other_business_and_user
        
        # Create project in other business
        other_project = models.Project(name="Other Project", business_id=other_business.id)
        db_session.add(other_project)
        db_session.commit()
        
        tag_data = {"project_id": other_project.id}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Project not found or access denied" in response.json()["detail"]
        assert "must belong to your business" in response.json()["detail"]


class TestDocumentTaggingAuthentication:
    """Test authentication scenarios"""

    def test_tag_document_unauthorized(self, client: TestClient, test_document):
        """Test tagging without authentication"""
        tag_data = {"client_id": 1}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data)
        
        assert response.status_code in [401, 403]

    def test_tag_document_invalid_token(self, client: TestClient, test_document):
        """Test tagging with invalid token"""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        tag_data = {"client_id": 1}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=invalid_headers)
        
        assert response.status_code in [401, 403]


class TestDocumentTaggingEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_tag_with_empty_payload(self, client: TestClient, test_document, auth_headers):
        """Test tagging with empty JSON payload"""
        response = client.put(f"/documents/{test_document.id}/tag", json={}, headers=auth_headers)
        
        assert response.status_code == 200
        # Should succeed but not change anything since all fields are optional

    def test_tag_document_multiple_times(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test tagging the same document multiple times"""
        test_client, test_project, test_category = test_client_project_category
        
        # First tagging
        tag_data1 = {"client_id": test_client.id}
        response1 = client.put(f"/documents/{test_document.id}/tag", json=tag_data1, headers=auth_headers)
        assert response1.status_code == 200
        
        # Second tagging with different data
        tag_data2 = {"project_id": test_project.id, "category_id": test_category.id}
        response2 = client.put(f"/documents/{test_document.id}/tag", json=tag_data2, headers=auth_headers)
        assert response2.status_code == 200
        
        # Verify final state
        data = response2.json()
        assert data["client_id"] == test_client.id  # Should preserve
        assert data["project_id"] == test_project.id
        assert data["category_id"] == test_category.id

    def test_tag_updates_timestamp(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test that tagging updates the document timestamp"""
        original_updated_at = test_document.updated_at
        
        test_client, _, _ = test_client_project_category
        tag_data = {"client_id": test_client.id}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 200
        
        # Verify timestamp was updated
        db_session.refresh(test_document)
        assert test_document.updated_at != original_updated_at

    def test_tag_with_zero_ids(self, client: TestClient, test_document, auth_headers):
        """Test tagging with ID value of 0"""
        tag_data = {"client_id": 0, "project_id": 0, "category_id": 0}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        # Should fail since ID 0 won't exist
        assert response.status_code == 400

    def test_tag_preserves_other_document_fields(self, client: TestClient, db_session, test_document, test_client_project_category, auth_headers):
        """Test that tagging doesn't affect other document fields"""
        original_filename = test_document.filename
        original_status = test_document.status
        original_user_id = test_document.user_id
        
        test_client, _, _ = test_client_project_category
        tag_data = {"client_id": test_client.id}
        
        response = client.put(f"/documents/{test_document.id}/tag", json=tag_data, headers=auth_headers)
        
        assert response.status_code == 200
        
        # Verify other fields are unchanged
        db_session.refresh(test_document)
        assert test_document.filename == original_filename
        assert test_document.status == original_status
        assert test_document.user_id == original_user_id