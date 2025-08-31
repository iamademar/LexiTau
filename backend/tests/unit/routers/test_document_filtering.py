"""
Unit tests for enhanced document filtering in GET /documents endpoint.
Tests tag-based filtering (client, project, category) and classification filtering.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

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
def test_tags_and_documents(db_session, test_business_and_user):
    """Create test clients, projects, categories and documents for filtering tests"""
    business, user = test_business_and_user
    
    # Create clients
    client1 = models.Client(name="Client A", business_id=business.id)
    client2 = models.Client(name="Client B", business_id=business.id)
    db_session.add_all([client1, client2])
    
    # Create projects  
    project1 = models.Project(name="Project X", business_id=business.id)
    project2 = models.Project(name="Project Y", business_id=business.id)
    db_session.add_all([project1, project2])
    
    # Create categories
    category1 = models.Category(name="Office Supplies")
    category2 = models.Category(name="Software")
    db_session.add_all([category1, category2])
    
    db_session.commit()
    db_session.refresh(client1)
    db_session.refresh(client2)
    db_session.refresh(project1)
    db_session.refresh(project2)
    db_session.refresh(category1)
    db_session.refresh(category2)
    
    # Create documents with different tag combinations and classifications
    docs = []
    
    # Document 1: Revenue, Client A, Project X, Category 1
    doc1 = models.Document(
        user_id=user.id,
        business_id=business.id,
        client_id=client1.id,
        project_id=project1.id,
        category_id=category1.id,
        filename="revenue_client_a.pdf",
        file_url="https://example.com/revenue_client_a.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        classification=DocumentClassification.REVENUE,
        status=DocumentStatus.COMPLETED
    )
    docs.append(doc1)
    
    # Document 2: Expense, Client A, no project, Category 2  
    doc2 = models.Document(
        user_id=user.id,
        business_id=business.id,
        client_id=client1.id,
        project_id=None,
        category_id=category2.id,
        filename="expense_client_a.pdf",
        file_url="https://example.com/expense_client_a.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.RECEIPT,
        classification=DocumentClassification.EXPENSE,
        status=DocumentStatus.COMPLETED
    )
    docs.append(doc2)
    
    # Document 3: Revenue, Client B, Project Y, no category
    doc3 = models.Document(
        user_id=user.id,
        business_id=business.id,
        client_id=client2.id,
        project_id=project2.id,
        category_id=None,
        filename="revenue_client_b.pdf",
        file_url="https://example.com/revenue_client_b.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        classification=DocumentClassification.REVENUE,
        status=DocumentStatus.COMPLETED
    )
    docs.append(doc3)
    
    # Document 4: Expense, no client, no project, Category 1 (untagged except category)
    doc4 = models.Document(
        user_id=user.id,
        business_id=business.id,
        client_id=None,
        project_id=None,
        category_id=category1.id,
        filename="untagged_expense.pdf", 
        file_url="https://example.com/untagged_expense.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.RECEIPT,
        classification=DocumentClassification.EXPENSE,
        status=DocumentStatus.COMPLETED
    )
    docs.append(doc4)
    
    # Document 5: Revenue, no tags at all (completely untagged)
    doc5 = models.Document(
        user_id=user.id,
        business_id=business.id,
        client_id=None,
        project_id=None,
        category_id=None,
        filename="fully_untagged_revenue.pdf",
        file_url="https://example.com/fully_untagged_revenue.pdf", 
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        classification=DocumentClassification.REVENUE,
        status=DocumentStatus.COMPLETED
    )
    docs.append(doc5)
    
    db_session.add_all(docs)
    db_session.commit()
    
    for doc in docs:
        db_session.refresh(doc)
    
    return {
        'clients': [client1, client2],
        'projects': [project1, project2], 
        'categories': [category1, category2],
        'documents': docs
    }


class TestClientFiltering:
    """Test client-based filtering"""

    def test_filter_by_client_id(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering documents by client ID"""
        data = test_tags_and_documents
        client_a = data['clients'][0]
        
        response = client.get(f"/documents/?client_id={client_a.id}", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 2 documents for Client A (doc1 and doc2)
        assert result["pagination"]["total_items"] == 2
        documents = result["documents"]
        
        for doc in documents:
            assert "client_a" in doc["filename"].lower()

    def test_filter_by_nonexistent_client(self, client: TestClient, auth_headers):
        """Test filtering by non-existent client ID returns error"""
        response = client.get("/documents/?client_id=99999", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Client not found or access denied" in response.json()["detail"]

    def test_filter_by_foreign_business_client(self, client: TestClient, db_session, test_tags_and_documents, other_business_and_user, auth_headers):
        """Test filtering by client from different business fails"""
        other_business, other_user = other_business_and_user
        
        # Create client in other business
        other_client = models.Client(name="Other Client", business_id=other_business.id)
        db_session.add(other_client)
        db_session.commit()
        
        response = client.get(f"/documents/?client_id={other_client.id}", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Client not found or access denied" in response.json()["detail"]


class TestProjectFiltering:
    """Test project-based filtering"""

    def test_filter_by_project_id(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering documents by project ID"""
        data = test_tags_and_documents
        project_x = data['projects'][0]
        
        response = client.get(f"/documents/?project_id={project_x.id}", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 1 document for Project X (doc1)
        assert result["pagination"]["total_items"] == 1
        documents = result["documents"]
        
        assert documents[0]["filename"] == "revenue_client_a.pdf"

    def test_filter_by_nonexistent_project(self, client: TestClient, auth_headers):
        """Test filtering by non-existent project ID returns error"""
        response = client.get("/documents/?project_id=99999", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Project not found or access denied" in response.json()["detail"]

    def test_filter_by_foreign_business_project(self, client: TestClient, db_session, test_tags_and_documents, other_business_and_user, auth_headers):
        """Test filtering by project from different business fails"""
        other_business, other_user = other_business_and_user
        
        # Create project in other business
        other_project = models.Project(name="Other Project", business_id=other_business.id)
        db_session.add(other_project)
        db_session.commit()
        
        response = client.get(f"/documents/?project_id={other_project.id}", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Project not found or access denied" in response.json()["detail"]


class TestCategoryFiltering:
    """Test category-based filtering"""

    def test_filter_by_category_id(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering documents by category ID"""
        data = test_tags_and_documents
        category1 = data['categories'][0]  # Office Supplies
        
        response = client.get(f"/documents/?category_id={category1.id}", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 2 documents with Category 1 (doc1 and doc4)
        assert result["pagination"]["total_items"] == 2

    def test_filter_by_nonexistent_category(self, client: TestClient, auth_headers):
        """Test filtering by non-existent category ID returns error"""
        response = client.get("/documents/?category_id=99999", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Category not found" in response.json()["detail"]


class TestClassificationFiltering:
    """Test classification-based filtering"""

    def test_filter_by_revenue_classification(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering documents by revenue classification"""
        response = client.get("/documents/?classification=REVENUE", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 3 revenue documents (doc1, doc3, doc5)
        assert result["pagination"]["total_items"] == 3
        
        for doc in result["documents"]:
            assert "revenue" in doc["filename"].lower()

    def test_filter_by_expense_classification(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering documents by expense classification"""
        response = client.get("/documents/?classification=EXPENSE", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 2 expense documents (doc2, doc4)
        assert result["pagination"]["total_items"] == 2
        
        for doc in result["documents"]:
            assert "expense" in doc["filename"].lower() or "untagged" in doc["filename"].lower()


class TestCombinedFiltering:
    """Test combining multiple filters"""

    def test_revenue_documents_for_specific_client(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test listing only revenue documents for a specific client"""
        data = test_tags_and_documents
        client_a = data['clients'][0]
        
        response = client.get(f"/documents/?classification=REVENUE&client_id={client_a.id}", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 1 document (doc1: revenue + Client A)
        assert result["pagination"]["total_items"] == 1
        doc = result["documents"][0]
        assert doc["filename"] == "revenue_client_a.pdf"

    def test_filter_by_client_and_project(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering by both client and project"""
        data = test_tags_and_documents
        client_a = data['clients'][0]
        project_x = data['projects'][0]
        
        response = client.get(f"/documents/?client_id={client_a.id}&project_id={project_x.id}", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 1 document (doc1: Client A + Project X)
        assert result["pagination"]["total_items"] == 1
        doc = result["documents"][0]
        assert doc["filename"] == "revenue_client_a.pdf"

    def test_filter_by_project_and_category(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering by project and category"""
        data = test_tags_and_documents
        project_x = data['projects'][0]
        category1 = data['categories'][0]
        
        response = client.get(f"/documents/?project_id={project_x.id}&category_id={category1.id}", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should return 1 document (doc1: Project X + Category 1)
        assert result["pagination"]["total_items"] == 1
        doc = result["documents"][0]
        assert doc["filename"] == "revenue_client_a.pdf"


class TestUntaggedDocuments:
    """Test filtering for untagged documents"""

    def test_list_all_untagged_documents(self, client: TestClient, db_session, test_business_and_user, auth_headers):
        """Test listing all untagged documents (no client, project, or category)"""
        business, user = test_business_and_user
        
        # Create fully untagged document
        untagged_doc = models.Document(
            user_id=user.id,
            business_id=business.id,
            client_id=None,
            project_id=None,
            category_id=None,
            filename="completely_untagged.pdf",
            file_url="https://example.com/completely_untagged.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(untagged_doc)
        db_session.commit()
        
        # This would require a special endpoint or query parameter to find untagged documents
        # For now we can't directly filter for NULL values through query params
        # This would need to be implemented as a special filter like "untagged=true"
        
        response = client.get("/documents/", headers=auth_headers)
        assert response.status_code == 200
        
        # We can at least verify the untagged document exists
        result = response.json()
        untagged_docs = [doc for doc in result["documents"] if doc["filename"] == "completely_untagged.pdf"]
        assert len(untagged_docs) == 1


class TestFilterValidationAndEdgeCases:
    """Test filter validation and edge cases"""

    def test_filter_with_zero_client_id(self, client: TestClient, auth_headers):
        """Test filtering with client_id=0"""
        response = client.get("/documents/?client_id=0", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Client not found or access denied" in response.json()["detail"]

    def test_multiple_classification_filters(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test that only last classification filter is used"""
        # FastAPI will use the last value for repeated query parameters
        response = client.get("/documents/?classification=REVENUE&classification=EXPENSE", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should filter by EXPENSE (last value)
        assert result["pagination"]["total_items"] == 2

    def test_filter_with_pagination(self, client: TestClient, test_tags_and_documents, auth_headers):
        """Test filtering works with pagination"""
        response = client.get("/documents/?classification=REVENUE&page=1&per_page=2", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["pagination"]["total_items"] == 3  # Total revenue documents
        assert len(result["documents"]) == 2  # Per page limit
        assert result["pagination"]["total_pages"] == 2

    def test_business_isolation_with_filters(self, client: TestClient, db_session, test_tags_and_documents, other_business_and_user, auth_headers):
        """Test that filters don't leak data between businesses"""
        data = test_tags_and_documents
        other_business, other_user = other_business_and_user
        
        # Create document in other business with same classification
        other_doc = models.Document(
            user_id=other_user.id,
            business_id=other_business.id,
            client_id=None,
            project_id=None,
            category_id=None,
            filename="other_business_revenue.pdf",
            file_url="https://example.com/other_business_revenue.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.REVENUE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(other_doc)
        db_session.commit()
        
        # Filter should only return documents from user's business
        response = client.get("/documents/?classification=REVENUE", headers=auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should only see documents from test business (3), not other business
        assert result["pagination"]["total_items"] == 3
        
        for doc in result["documents"]:
            assert "other_business" not in doc["filename"]