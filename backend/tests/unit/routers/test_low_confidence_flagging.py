"""
Tests for low confidence flagging functionality.
Tests that fields with confidence < 0.7 are flagged as is_low_confidence = True.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from decimal import Decimal
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.main import app
from app.models import Business, User, Document, ExtractedField, LineItem
from app.enums import DocumentStatus, DocumentType, FileType, DocumentClassification
from app.auth import create_access_token, get_password_hash
from app.db import get_db, Base
from app.routers.documents import is_low_confidence


# Create in-memory SQLite database for testing to avoid PostgreSQL timeout issues
SQLITE_DATABASE_URL = "sqlite:///./test_low_confidence_flagging.db"
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


class TestLowConfidenceFlagging:
    """Test low confidence flagging functionality"""
    
    def test_is_low_confidence_function(self):
        """Test the is_low_confidence helper function"""
        # Test various confidence scores
        assert is_low_confidence(None) == True  # None should be low confidence
        assert is_low_confidence(0.0) == True   # 0.0 < 0.7
        assert is_low_confidence(0.3) == True   # 0.3 < 0.7
        assert is_low_confidence(0.6) == True   # 0.6 < 0.7
        assert is_low_confidence(0.69) == True  # 0.69 < 0.7
        
        # These should NOT be low confidence
        assert is_low_confidence(0.7) == False  # 0.7 = 0.7 (not less than)
        assert is_low_confidence(0.8) == False  # 0.8 > 0.7
        assert is_low_confidence(0.95) == False # 0.95 > 0.7
        assert is_low_confidence(1.0) == False  # 1.0 > 0.7

    def test_mixed_confidence_scores_in_fields(self, db_session: Session, test_user_and_token):
        """Test document with mixed confidence scores in extracted fields"""
        test_user, token = test_user_and_token
        
        # Create a completed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="mixed_confidence_invoice.pdf",
            file_url="https://example.com/mixed_confidence_invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.75
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add extracted fields with mixed confidence scores
        fields_data = [
            {"field_name": "vendor_name", "value": "High Confidence Corp", "confidence": 0.95},      # High confidence
            {"field_name": "invoice_number", "value": "INV-001", "confidence": 0.8},                 # High confidence  
            {"field_name": "total_amount", "value": "1000.00", "confidence": 0.7},                   # Exactly at threshold
            {"field_name": "invoice_date", "value": "2024-01-15", "confidence": 0.65},               # Low confidence
            {"field_name": "tax_amount", "value": "80.00", "confidence": 0.3},                       # Very low confidence
            {"field_name": "due_date", "value": "Unclear date", "confidence": None},                 # No confidence (None)
        ]
        
        for field_data in fields_data:
            field = ExtractedField(
                document_id=document.id,
                business_id=test_user.business_id,
                **field_data
            )
            db_session.add(field)
        
        db_session.commit()
        
        # Make request to get document fields
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check extracted fields flagging
        fields = data["extracted_fields"]
        assert len(fields) == 6
        
        # Create lookup for easier testing
        field_lookup = {f["field_name"]: f for f in fields}
        
        # Test high confidence fields (should NOT be flagged)
        vendor_field = field_lookup["vendor_name"]
        assert vendor_field["confidence"] == 0.95
        assert vendor_field["is_low_confidence"] == False
        
        invoice_num_field = field_lookup["invoice_number"]
        assert invoice_num_field["confidence"] == 0.8
        assert invoice_num_field["is_low_confidence"] == False
        
        # Test exactly at threshold (0.7 should NOT be flagged as low confidence)
        total_field = field_lookup["total_amount"]
        assert total_field["confidence"] == 0.7
        assert total_field["is_low_confidence"] == False
        
        # Test low confidence fields (should be flagged)
        date_field = field_lookup["invoice_date"]
        assert date_field["confidence"] == 0.65
        assert date_field["is_low_confidence"] == True
        
        tax_field = field_lookup["tax_amount"]
        assert tax_field["confidence"] == 0.3
        assert tax_field["is_low_confidence"] == True
        
        # Test None confidence (should be flagged)
        due_date_field = field_lookup["due_date"]
        assert due_date_field["confidence"] is None
        assert due_date_field["is_low_confidence"] == True

    def test_mixed_confidence_scores_in_line_items(self, db_session: Session, test_user_and_token):
        """Test document with mixed confidence scores in line items"""
        test_user, token = test_user_and_token
        
        # Create a completed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="mixed_line_items.pdf",
            file_url="https://example.com/mixed_line_items.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.RECEIPT,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.72
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add line items with mixed confidence scores
        line_items_data = [
            {
                "description": "Clear Item Description",
                "quantity": Decimal("2"),
                "unit_price": Decimal("50.00"),
                "total": Decimal("100.00"),
                "confidence": 0.92  # High confidence
            },
            {
                "description": "Somewhat Clear Item",
                "quantity": Decimal("1"),
                "unit_price": Decimal("25.00"),
                "total": Decimal("25.00"),
                "confidence": 0.7  # Exactly at threshold
            },
            {
                "description": "Unclear Item",
                "quantity": Decimal("3"),
                "unit_price": Decimal("10.00"),
                "total": Decimal("30.00"),
                "confidence": 0.55  # Low confidence
            },
            {
                "description": "Very Unclear Item",
                "quantity": Decimal("1"),
                "unit_price": Decimal("15.00"),
                "total": Decimal("15.00"),
                "confidence": 0.2  # Very low confidence
            },
            {
                "description": "No Confidence Item",
                "quantity": Decimal("1"),
                "unit_price": Decimal("5.00"),
                "total": Decimal("5.00"),
                "confidence": None  # No confidence
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
        
        # Make request to get document fields
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check line items flagging
        line_items = data["line_items"]
        assert len(line_items) == 5
        
        # Test high confidence item (should NOT be flagged)
        clear_item = next(item for item in line_items if item["description"] == "Clear Item Description")
        assert clear_item["confidence"] == 0.92
        assert clear_item["is_low_confidence"] == False
        
        # Test exactly at threshold (should NOT be flagged)
        threshold_item = next(item for item in line_items if item["description"] == "Somewhat Clear Item")
        assert threshold_item["confidence"] == 0.7
        assert threshold_item["is_low_confidence"] == False
        
        # Test low confidence items (should be flagged)
        unclear_item = next(item for item in line_items if item["description"] == "Unclear Item")
        assert unclear_item["confidence"] == 0.55
        assert unclear_item["is_low_confidence"] == True
        
        very_unclear_item = next(item for item in line_items if item["description"] == "Very Unclear Item")
        assert very_unclear_item["confidence"] == 0.2
        assert very_unclear_item["is_low_confidence"] == True
        
        # Test None confidence (should be flagged)
        no_confidence_item = next(item for item in line_items if item["description"] == "No Confidence Item")
        assert no_confidence_item["confidence"] is None
        assert no_confidence_item["is_low_confidence"] == True

    def test_all_high_confidence_fields(self, db_session: Session, test_user_and_token):
        """Test document where all fields have high confidence"""
        test_user, token = test_user_and_token
        
        # Create a completed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="high_confidence_invoice.pdf",
            file_url="https://example.com/high_confidence_invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.95
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add extracted fields with high confidence scores
        fields_data = [
            {"field_name": "vendor_name", "value": "Perfect Corp", "confidence": 0.98},
            {"field_name": "total_amount", "value": "500.00", "confidence": 0.95},
            {"field_name": "invoice_date", "value": "2024-01-15", "confidence": 0.92}
        ]
        
        for field_data in fields_data:
            field = ExtractedField(
                document_id=document.id,
                business_id=test_user.business_id,
                **field_data
            )
            db_session.add(field)
        
        db_session.commit()
        
        # Make request
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # All fields should have is_low_confidence = False
        fields = data["extracted_fields"]
        for field in fields:
            assert field["is_low_confidence"] == False
            assert field["confidence"] >= 0.7

    def test_all_low_confidence_fields(self, db_session: Session, test_user_and_token):
        """Test document where all fields have low confidence"""
        test_user, token = test_user_and_token
        
        # Create a completed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="low_confidence_invoice.pdf",
            file_url="https://example.com/low_confidence_invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.45
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add extracted fields with low confidence scores
        fields_data = [
            {"field_name": "vendor_name", "value": "Unclear Corp", "confidence": 0.6},
            {"field_name": "total_amount", "value": "???", "confidence": 0.2},
            {"field_name": "invoice_date", "value": "Unreadable", "confidence": 0.1}
        ]
        
        for field_data in fields_data:
            field = ExtractedField(
                document_id=document.id,
                business_id=test_user.business_id,
                **field_data
            )
            db_session.add(field)
        
        db_session.commit()
        
        # Make request
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # All fields should have is_low_confidence = True
        fields = data["extracted_fields"]
        for field in fields:
            assert field["is_low_confidence"] == True
            assert field["confidence"] < 0.7

    def test_edge_case_confidence_values(self, db_session: Session, test_user_and_token):
        """Test edge cases around the 0.7 threshold"""
        test_user, token = test_user_and_token
        
        # Create a completed document
        document = Document(
            user_id=test_user.id,
            business_id=test_user.business_id,
            filename="edge_case_confidence.pdf",
            file_url="https://example.com/edge_case_confidence.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
            confidence_score=0.7
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Add extracted fields with edge case confidence scores
        fields_data = [
            {"field_name": "exactly_threshold", "value": "Exactly 0.7", "confidence": 0.7},
            {"field_name": "just_above", "value": "Just above", "confidence": 0.700001},
            {"field_name": "just_below", "value": "Just below", "confidence": 0.699999},
            {"field_name": "zero_confidence", "value": "Zero", "confidence": 0.0},
            {"field_name": "perfect_confidence", "value": "Perfect", "confidence": 1.0}
        ]
        
        for field_data in fields_data:
            field = ExtractedField(
                document_id=document.id,
                business_id=test_user.business_id,
                **field_data
            )
            db_session.add(field)
        
        db_session.commit()
        
        # Make request
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/documents/{document.id}/fields", headers=headers)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        field_lookup = {f["field_name"]: f for f in data["extracted_fields"]}
        
        # Exactly 0.7 should NOT be flagged as low confidence
        assert field_lookup["exactly_threshold"]["confidence"] == 0.7
        assert field_lookup["exactly_threshold"]["is_low_confidence"] == False
        
        # Just above 0.7 should NOT be flagged
        assert field_lookup["just_above"]["confidence"] > 0.7
        assert field_lookup["just_above"]["is_low_confidence"] == False
        
        # Just below 0.7 should be flagged
        assert field_lookup["just_below"]["confidence"] < 0.7
        assert field_lookup["just_below"]["is_low_confidence"] == True
        
        # Zero confidence should be flagged
        assert field_lookup["zero_confidence"]["confidence"] == 0.0
        assert field_lookup["zero_confidence"]["is_low_confidence"] == True
        
        # Perfect confidence should NOT be flagged
        assert field_lookup["perfect_confidence"]["confidence"] == 1.0
        assert field_lookup["perfect_confidence"]["is_low_confidence"] == False