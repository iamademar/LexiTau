"""
Tests for GET /documents/{id}/fields endpoint.
Tests both completed and pending document states.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from uuid import uuid4
from decimal import Decimal
import sys
import os
from unittest.mock import Mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock Azure dependencies before importing app
sys.modules['azure.ai.documentintelligence'] = Mock()
sys.modules['azure.ai.documentintelligence.models'] = Mock()
sys.modules['azure.core.credentials'] = Mock()
sys.modules['azure.core.exceptions'] = Mock()

from app.main import app
from app.models import Business, User, Document, ExtractedField, LineItem
from app.enums import DocumentStatus, DocumentType, FileType, DocumentClassification
from app.auth import create_access_token, get_password_hash
from app.db import get_db, Base


# Create in-memory SQLite database for testing to avoid PostgreSQL timeout issues
SQLITE_DATABASE_URL = "sqlite:///./test_documents.db"
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
        db.query(ExtractedField).delete()  
        db.query(Document).delete()
        db.query(User).delete()
        db.query(Business).delete()
        db.commit()
        db.close()


@pytest.fixture
def test_user_and_token(db_session):
    """Create a test user and JWT token"""
    # Create business first
    business = Business(name="Test Business")
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    
    # Create user
    user = User(
        email="testuser@example.com",
        password_hash=get_password_hash("testpassword123"),
        business_id=business.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create JWT token
    token = create_access_token(data={"sub": user.email})
    
    return user, token


class TestGetDocumentFields:
    """Test GET /documents/{id}/fields endpoint"""
    
    def test_get_completed_document_fields_success(self, db_session: Session, test_user_and_token):
        """Test getting fields from a completed document with extracted data"""
        test_user, token = test_user_and_token
        
        # Create a completed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="test_invoice.pdf",
            file_url="https://example.com/test_invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.92
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add extracted fields
        fields_data = [
            {"field_name": "vendor_name", "value": "ACME Corp", "confidence": 0.95},
            {"field_name": "invoice_number", "value": "INV-001", "confidence": 0.92},
            {"field_name": "total_amount", "value": "1080.00", "confidence": 0.98},
            {"field_name": "invoice_date", "value": "2024-01-15", "confidence": 0.90},
            {"field_name": "tax_amount", "value": "80.00", "confidence": 0.89}
        ]
        
        for field_data in fields_data:
            field = ExtractedField(
                document_id=document.id,
                business_id=test_user.business_id,
                **field_data
            )
            db_session.add(field)
        
        # Add line items
        line_items_data = [
            {
                "description": "Software License",
                "quantity": Decimal("1"),
                "unit_price": Decimal("1000.00"),
                "total": Decimal("1000.00"),
                "confidence": 0.94
            },
            {
                "description": "Consulting Service",
                "quantity": Decimal("2"),
                "unit_price": Decimal("40.00"),
                "total": Decimal("80.00"),
                "confidence": 0.91
            }
        ]
        
        for item_data in line_items_data:
            line_item = LineItem(
                document_id=document.id,
                business_id=test_user.business_id,
                **item_data
            )
            db_session.add(line_item)
        
        db_session.commit()
        
        # Use token from fixture
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make request
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "document_id" in data
        assert "document_info" in data
        assert "extracted_fields" in data
        assert "line_items" in data
        assert "processing_status" in data
        assert "overall_confidence" in data
        assert "fields_summary" in data
        assert "line_items_summary" in data
        
        # Check document info
        assert data["document_id"] == str(document.id)
        assert data["processing_status"] == "COMPLETED"
        assert data["overall_confidence"] == 0.92
        
        doc_info = data["document_info"]
        assert doc_info["filename"] == "test_invoice.pdf"
        assert doc_info["document_type"] == "INVOICE"
        assert doc_info["status"] == "COMPLETED"
        
        # Check extracted fields
        fields = data["extracted_fields"]
        assert len(fields) == 5
        
        vendor_field = next(f for f in fields if f["field_name"] == "vendor_name")
        assert vendor_field["value"] == "ACME Corp"
        assert vendor_field["confidence"] == 0.95
        
        total_field = next(f for f in fields if f["field_name"] == "total_amount")
        assert total_field["value"] == "1080.00"
        assert total_field["confidence"] == 0.98
        
        # Check line items
        line_items = data["line_items"]
        assert len(line_items) == 2
        
        software_item = next(item for item in line_items if item["description"] == "Software License")
        assert software_item["quantity"] == 1.0
        assert software_item["unit_price"] == 1000.0
        assert software_item["total"] == 1000.0
        assert software_item["confidence"] == 0.94
        
        # Check summaries
        fields_summary = data["fields_summary"]
        assert fields_summary["total_fields"] == 5
        assert fields_summary["fields_with_values"] == 5
        assert fields_summary["fields_without_values"] == 0
        assert fields_summary["high_confidence_fields"] == 5  # >= 0.8 (all fields have >= 0.89)
        
        line_items_summary = data["line_items_summary"]
        assert line_items_summary["total_line_items"] == 2
        assert line_items_summary["items_with_descriptions"] == 2
        assert line_items_summary["items_with_totals"] == 2
        assert line_items_summary["total_amount"] == 1080.0

    def test_get_pending_document_fields_success(self, db_session: Session, test_user_and_token):
        """Test getting fields from a pending document (no extracted data yet)"""
        test_user, token = test_user_and_token
        
        # Create a pending document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="pending_receipt.pdf",
            file_url="https://example.com/pending_receipt.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.RECEIPT,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.PENDING,
            confidence_score=None
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Use token from fixture
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make request
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check basic structure
        assert data["document_id"] == str(document.id)
        assert data["processing_status"] == "PENDING"
        assert data["overall_confidence"] is None
        
        # Document info should be present
        doc_info = data["document_info"]
        assert doc_info["filename"] == "pending_receipt.pdf"
        assert doc_info["document_type"] == "RECEIPT"
        assert doc_info["status"] == "PENDING"
        
        # No extracted fields or line items yet
        assert data["extracted_fields"] == []
        assert data["line_items"] == []
        
        # Summaries should show empty state
        fields_summary = data["fields_summary"]
        assert fields_summary["total_fields"] == 0
        assert fields_summary["fields_with_values"] == 0
        assert fields_summary["average_confidence"] == 0.0
        
        line_items_summary = data["line_items_summary"]
        assert line_items_summary["total_line_items"] == 0
        assert line_items_summary["total_amount"] == 0.0

    def test_get_processing_document_fields_success(self, db_session: Session, test_user_and_token):
        """Test getting fields from a document currently being processed"""
        test_user, token = test_user_and_token
        
        # Create a processing document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="processing_invoice.pdf", 
            file_url="https://example.com/processing_invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.PROCESSING,
            confidence_score=None
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Use token from fixture
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make request
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["processing_status"] == "PROCESSING"
        assert data["overall_confidence"] is None
        assert data["extracted_fields"] == []
        assert data["line_items"] == []

    def test_get_failed_document_fields_success(self, db_session: Session, test_user_and_token):
        """Test getting fields from a failed document"""
        test_user, token = test_user_and_token
        
        # Create a failed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="failed_document.pdf",
            file_url="https://example.com/failed_document.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.FAILED,
            confidence_score=0.0
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Use token from fixture
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make request
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["processing_status"] == "FAILED"
        assert data["overall_confidence"] == 0.0
        assert data["extracted_fields"] == []
        assert data["line_items"] == []

    def test_get_document_fields_not_found(self, test_user_and_token):
        """Test getting fields for non-existent document"""
        test_user, token = test_user_and_token
        non_existent_id = uuid4()
        
        # Use token from fixture
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make request
        response = client.get(f"/documents/{non_existent_id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_document_fields_access_denied(self, db_session: Session, test_user_and_token):
        """Test access denied when trying to access another business's document"""
        test_user, _ = test_user_and_token
        
        # Create another business and user
        other_business = Business(name="Other Business")
        db_session.add(other_business)
        db_session.commit()
        
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            business_id=other_business.id
        )
        db_session.add(other_user)
        db_session.commit()
        
        # Create document for other business
        other_document = Document(
            user_id=other_user.id,
            business_id=other_business.id,
            filename="other_invoice.pdf",
            file_url="https://example.com/other_invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(other_document)
        db_session.commit()
        
        # Try to access with original user's token
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(f"/documents/{other_document.id}/fields", headers=headers)
        
        # Should be denied
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_document_fields_unauthorized(self, db_session: Session, test_user_and_token):
        """Test unauthorized access without token"""
        test_user, _ = test_user_and_token
        
        # Create a document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="test.pdf",
            file_url="https://example.com/test.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(document)
        db_session.commit()
        
        # Make request without token
        response = client.get(f"/documents/{document.id}/fields")
        
        # Should be unauthorized (403 is also acceptable for forbidden access)
        assert response.status_code in [401, 403]

    def test_get_document_fields_with_partial_data(self, db_session: Session, test_user_and_token):
        """Test getting fields from document with some missing/null values"""
        test_user, _ = test_user_and_token
        
        # Create document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="partial_data.pdf",
            file_url="https://example.com/partial_data.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.RECEIPT,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.75
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add fields with some missing values
        fields_data = [
            {"field_name": "merchant_name", "value": "Coffee Shop", "confidence": 0.95},
            {"field_name": "total_amount", "value": None, "confidence": 0.0},  # Missing value
            {"field_name": "tax_amount", "value": "", "confidence": 0.0},  # Empty value
            {"field_name": "transaction_date", "value": "2024-01-20", "confidence": 0.88}
        ]
        
        for field_data in fields_data:
            field = ExtractedField(
                document_id=document.id,
                business_id=test_user.business_id,
                **field_data
            )
            db_session.add(field)
        
        # Add line item with partial data
        line_item = LineItem(
            document_id=document.id,
            business_id=test_user.business_id,
            description="Coffee",
            quantity=None,  # Missing quantity
            unit_price=None,  # Missing unit price
            total=Decimal("5.50"),
            confidence=0.80
        )
        db_session.add(line_item)
        db_session.commit()
        
        # Create access token and make request
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check fields summary accounts for missing values
        fields_summary = data["fields_summary"]
        assert fields_summary["total_fields"] == 4
        assert fields_summary["fields_with_values"] == 2  # Only non-null, non-empty values
        assert fields_summary["fields_without_values"] == 2
        
        # Check line items summary
        line_items_summary = data["line_items_summary"]
        assert line_items_summary["total_line_items"] == 1
        assert line_items_summary["items_with_descriptions"] == 1
        assert line_items_summary["items_with_totals"] == 1
        assert line_items_summary["total_amount"] == 5.5
        
        # Check individual line item values
        line_item_response = data["line_items"][0]
        assert line_item_response["description"] == "Coffee"
        assert line_item_response["quantity"] is None
        assert line_item_response["unit_price"] is None
        assert line_item_response["total"] == 5.5

    def test_get_document_fields_invalid_uuid(self, test_user_and_token):
        """Test getting fields with invalid document UUID"""
        _, token = test_user_and_token
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make request with invalid UUID
        response = client.get("/documents/invalid-uuid/fields", headers=headers)
        
        # Should return 422 for validation error
        assert response.status_code == 422