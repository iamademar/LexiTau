"""
Tests for PUT /documents/{document_id}/line-items/{item_id} endpoint.
Tests all aspects including validation, authentication, authorization, and business logic.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from uuid import uuid4
from decimal import Decimal
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.main import app
from app.models import Business, User, Document, LineItem
from app.enums import DocumentStatus, DocumentType, FileType, DocumentClassification
from app.auth import create_access_token, get_password_hash
from app.db import get_db, Base
from app.schemas import LineItemUpdateRequest


# Create in-memory SQLite database for testing to avoid PostgreSQL timeout issues
SQLITE_DATABASE_URL = "sqlite:///./test_line_item_updates.db"
engine = create_engine(SQLITE_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Create tables and override dependency
Base.metadata.create_all(bind=engine)
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        # Clean up test data
        db.query(LineItem).delete()
        db.query(Document).delete()
        db.query(User).delete()
        db.query(Business).delete()
        db.commit()
        db.close()


@pytest.fixture
def test_user_and_token(db_session):
    """Create a test user and return both user and auth token"""
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]
    
    business = Business(name=f"Test Business {unique_suffix}")
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    
    user = User(
        email=f"test_{unique_suffix}@example.com",
        password_hash=get_password_hash("testpassword123"),
        business_id=business.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    token = create_access_token(data={"sub": user.email})
    
    return user, token


@pytest.fixture
def completed_document_with_line_item(test_user_and_token, db_session):
    """Create a completed document with a line item for testing"""
    user, token = test_user_and_token
    
    document = Document(
        user_id=user.id,
        business_id=user.business_id,
        filename="test_invoice.pdf",
        file_url="https://example.com/test.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        classification=DocumentClassification.EXPENSE,
        status=DocumentStatus.COMPLETED
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    line_item = LineItem(
        document_id=document.id,
        business_id=user.business_id,
        description="Original Item",
        quantity=Decimal("2"),
        unit_price=Decimal("50.00"),
        total=Decimal("100.00"),
        confidence=0.95
    )
    db_session.add(line_item)
    db_session.commit()
    db_session.refresh(line_item)
    
    return document, line_item, user, token


class TestLineItemUpdateRequest:
    """Test the LineItemUpdateRequest schema validation"""
    
    def test_valid_full_request(self):
        """Test valid request with all fields"""
        request = LineItemUpdateRequest(
            description="Office Chair",
            quantity=Decimal("2"),
            unit_price=Decimal("150"),
            total=Decimal("300")
        )
        assert request.description == "Office Chair"
        assert request.quantity == Decimal("2")
        assert request.unit_price == Decimal("150")
        assert request.total == Decimal("300")
    
    def test_valid_partial_request(self):
        """Test valid request with only some fields"""
        request = LineItemUpdateRequest(description="Updated Description")
        assert request.description == "Updated Description"
        assert request.quantity is None
        assert request.unit_price is None
        assert request.total is None
    
    def test_negative_quantity_rejected(self):
        """Test that negative quantity is rejected"""
        with pytest.raises(ValueError):
            LineItemUpdateRequest(quantity=Decimal("-1"))
    
    def test_negative_unit_price_rejected(self):
        """Test that negative unit price is rejected"""
        with pytest.raises(ValueError):
            LineItemUpdateRequest(unit_price=Decimal("-50"))
    
    def test_negative_total_rejected(self):
        """Test that negative total is rejected"""
        with pytest.raises(ValueError):
            LineItemUpdateRequest(total=Decimal("-100"))
    
    def test_zero_values_accepted(self):
        """Test that zero values are accepted"""
        request = LineItemUpdateRequest(
            quantity=Decimal("0"),
            unit_price=Decimal("0"),
            total=Decimal("0")
        )
        assert request.quantity == Decimal("0")
        assert request.unit_price == Decimal("0")
        assert request.total == Decimal("0")


class TestLineItemUpdateEndpoint:
    """Test the PUT /documents/{document_id}/line-items/{item_id} endpoint"""
    
    def test_successful_full_update(self, completed_document_with_line_item):
        """Test successful update of all line item fields"""
        document, line_item, user, token = completed_document_with_line_item
        
        headers = {"Authorization": f"Bearer {token}"}
        update_data = {
            "description": "Updated Office Chair",
            "quantity": 3,
            "unit_price": 175.50,
            "total": 526.50
        }
        
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "successfully" in data["message"]
        assert data["document_id"] == str(document.id)
        
        # Check updated line item data
        updated_item = data["line_item"]
        assert updated_item["description"] == "Updated Office Chair"
        assert updated_item["quantity"] == 3.0
        assert updated_item["unit_price"] == 175.5
        assert updated_item["total"] == 526.5
    
    def test_successful_partial_update(self, completed_document_with_line_item):
        """Test successful partial update (only description)"""
        document, line_item, user, token = completed_document_with_line_item
        
        headers = {"Authorization": f"Bearer {token}"}
        update_data = {"description": "Just Updated Description"}
        
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        updated_item = data["line_item"]
        assert updated_item["description"] == "Just Updated Description"
        # Original values should be preserved
        assert updated_item["quantity"] == 2.0
        assert updated_item["unit_price"] == 50.0
        assert updated_item["total"] == 100.0
    
    def test_no_authentication_rejected(self, completed_document_with_line_item):
        """Test that requests without authentication are rejected"""
        document, line_item, user, token = completed_document_with_line_item
        
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]
    
    def test_invalid_token_rejected(self, completed_document_with_line_item):
        """Test that requests with invalid tokens are rejected"""
        document, line_item, user, token = completed_document_with_line_item
        
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 401
    
    def test_nonexistent_document_rejected(self, test_user_and_token):
        """Test that non-existent document returns 404"""
        user, token = test_user_and_token
        
        headers = {"Authorization": f"Bearer {token}"}
        fake_doc_id = uuid4()
        
        response = client.put(
            f"/documents/{fake_doc_id}/line-items/1",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_wrong_business_access_denied(self, completed_document_with_line_item, db_session):
        """Test that user from different business cannot access document"""
        import uuid
        document, line_item, user, token = completed_document_with_line_item
        
        # Create user from different business
        unique_suffix = str(uuid.uuid4())[:8]
        other_business = Business(name=f"Other Business {unique_suffix}")
        db_session.add(other_business)
        db_session.commit()
        
        other_user = User(
            email=f"other_{unique_suffix}@example.com",
            password_hash=get_password_hash("testpassword123"),
            business_id=other_business.id
        )
        db_session.add(other_user)
        db_session.commit()
        
        other_token = create_access_token(data={"sub": other_user.email})
        
        headers = {"Authorization": f"Bearer {other_token}"}
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_pending_document_rejected(self, test_user_and_token, db_session):
        """Test that documents not in COMPLETED status are rejected"""
        user, token = test_user_and_token
        
        # Create document in PENDING status
        pending_doc = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="pending.pdf",
            file_url="https://example.com/pending.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.PENDING
        )
        db_session.add(pending_doc)
        db_session.commit()
        db_session.refresh(pending_doc)
        
        line_item = LineItem(
            document_id=pending_doc.id,
            business_id=user.business_id,
            description="Test Item",
            quantity=Decimal("1"),
            unit_price=Decimal("100"),
            total=Decimal("100")
        )
        db_session.add(line_item)
        db_session.commit()
        db_session.refresh(line_item)
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            f"/documents/{pending_doc.id}/line-items/{line_item.id}",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 400
        assert "COMPLETED" in response.json()["detail"]
    
    def test_nonexistent_line_item_rejected(self, completed_document_with_line_item):
        """Test that non-existent line item returns 404"""
        document, line_item, user, token = completed_document_with_line_item
        
        headers = {"Authorization": f"Bearer {token}"}
        fake_item_id = 99999
        
        response = client.put(
            f"/documents/{document.id}/line-items/{fake_item_id}",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_line_item_from_different_document_rejected(self, completed_document_with_line_item, db_session):
        """Test that line item from different document is rejected"""
        document, line_item, user, token = completed_document_with_line_item
        
        # Create another document with its own line item
        other_doc = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="other.pdf",
            file_url="https://example.com/other.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(other_doc)
        db_session.commit()
        db_session.refresh(other_doc)
        
        other_line_item = LineItem(
            document_id=other_doc.id,
            business_id=user.business_id,
            description="Other Item",
            quantity=Decimal("1"),
            unit_price=Decimal("200"),
            total=Decimal("200")
        )
        db_session.add(other_line_item)
        db_session.commit()
        db_session.refresh(other_line_item)
        
        headers = {"Authorization": f"Bearer {token}"}
        # Try to update other_line_item using wrong document ID
        response = client.put(
            f"/documents/{document.id}/line-items/{other_line_item.id}",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_empty_update_rejected(self, completed_document_with_line_item):
        """Test that empty update request is rejected"""
        document, line_item, user, token = completed_document_with_line_item
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json={}
        )
        
        assert response.status_code == 400
        assert "at least one field" in response.json()["detail"].lower()
    
    def test_invalid_uuid_format_rejected(self, test_user_and_token):
        """Test that invalid UUID format is rejected"""
        user, token = test_user_and_token
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            "/documents/invalid-uuid/line-items/1",
            headers=headers,
            json={"description": "Should fail"}
        )
        
        assert response.status_code == 422
    
    def test_negative_values_rejected(self, completed_document_with_line_item):
        """Test that negative values are rejected by schema validation"""
        document, line_item, user, token = completed_document_with_line_item
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test negative quantity
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json={"quantity": -1}
        )
        
        assert response.status_code == 422
        
        # Test negative unit_price
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json={"unit_price": -50}
        )
        
        assert response.status_code == 422
        
        # Test negative total
        response = client.put(
            f"/documents/{document.id}/line-items/{line_item.id}",
            headers=headers,
            json={"total": -100}
        )
        
        assert response.status_code == 422