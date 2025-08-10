"""
Tests for FieldCorrection model functionality.
Tests correction creation, relationships, and data integrity.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import uuid4

from app.main import app
from app.models import Business, User, Document, ExtractedField, FieldCorrection
from app.enums import DocumentStatus, DocumentType, FileType
from app.auth import create_user_and_business
from app.test_db import get_test_db, create_test_tables, drop_test_tables
from app.db import get_db


client = TestClient(app)

# Override the dependency for testing to use the test database
app.dependency_overrides[get_db] = lambda: next(get_test_db())


@pytest.fixture(scope="module")
def setup_database():
    create_test_tables()
    yield
    drop_test_tables()


@pytest.fixture
def db_session(setup_database):
    db = next(get_test_db())
    try:
        yield db
    finally:
        # Clean up test data
        db.query(FieldCorrection).delete()
        db.query(ExtractedField).delete()
        db.query(Document).delete()
        db.query(User).delete()
        db.query(Business).delete()
        db.commit()
        db.close()


@pytest.fixture
def test_user_and_document(db_session):
    """Create a test user and document for correction tests"""
    user = create_user_and_business(
        db=db_session,
        email="corrector@example.com",
        password="testpassword123",
        business_name="Correction Test Business"
    )
    
    document = Document(
        user_id=user.id,
        business_id=user.business_id,
        filename="test_invoice.pdf",
        file_url="https://example.com/test_invoice.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.COMPLETED,
        confidence_score=0.85
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    return user, document


class TestFieldCorrectionModel:
    """Test FieldCorrection model functionality"""
    
    def test_field_correction_creation(self, db_session: Session, test_user_and_document):
        """Test basic field correction creation"""
        user, document = test_user_and_document
        
        # Create a field correction
        correction = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="Acme Corp",
            corrected_value="ACME Corporation",
            corrected_by=user.id
        )
        
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)
        
        # Verify correction was created
        assert correction.id is not None
        assert correction.document_id == document.id
        assert correction.field_name == "vendor_name"
        assert correction.original_value == "Acme Corp"
        assert correction.corrected_value == "ACME Corporation"
        assert correction.corrected_by == user.id
        assert correction.timestamp is not None
        assert isinstance(correction.timestamp, datetime)

    def test_field_correction_with_null_original_value(self, db_session: Session, test_user_and_document):
        """Test correction where original value was null/empty"""
        user, document = test_user_and_document
        
        correction = FieldCorrection(
            document_id=document.id,
            field_name="invoice_number",
            original_value=None,  # OCR didn't extract anything
            corrected_value="INV-2024-001",
            corrected_by=user.id
        )
        
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)
        
        assert correction.original_value is None
        assert correction.corrected_value == "INV-2024-001"

    def test_field_correction_relationships(self, db_session: Session, test_user_and_document):
        """Test relationships between FieldCorrection, Document, and User"""
        user, document = test_user_and_document
        
        correction = FieldCorrection(
            document_id=document.id,
            field_name="total_amount",
            original_value="$100.00",
            corrected_value="$150.00",
            corrected_by=user.id
        )
        
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)
        
        # Test document relationship
        assert correction.document is not None
        assert correction.document.id == document.id
        assert correction.document.filename == "test_invoice.pdf"
        
        # Test user relationship
        assert correction.corrected_by_user is not None
        assert correction.corrected_by_user.id == user.id
        assert correction.corrected_by_user.email == "corrector@example.com"
        
        # Test reverse relationships
        document_corrections = document.field_corrections
        assert len(document_corrections) == 1
        assert document_corrections[0].id == correction.id
        
        user_corrections = user.field_corrections
        assert len(user_corrections) == 1
        assert user_corrections[0].id == correction.id

    def test_multiple_corrections_for_document(self, db_session: Session, test_user_and_document):
        """Test multiple corrections for the same document"""
        user, document = test_user_and_document
        
        corrections_data = [
            {
                "field_name": "vendor_name",
                "original_value": "ABC Inc",
                "corrected_value": "ABC Incorporated"
            },
            {
                "field_name": "invoice_date",
                "original_value": "2024-01-01",
                "corrected_value": "2024-01-15"
            },
            {
                "field_name": "total_amount",
                "original_value": "$999.99",
                "corrected_value": "$1,099.99"
            }
        ]
        
        created_corrections = []
        for data in corrections_data:
            correction = FieldCorrection(
                document_id=document.id,
                corrected_by=user.id,
                **data
            )
            db_session.add(correction)
            created_corrections.append(correction)
        
        db_session.commit()
        
        # Refresh all corrections
        for correction in created_corrections:
            db_session.refresh(correction)
        
        # Verify all corrections exist
        document_corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id
        ).all()
        
        assert len(document_corrections) == 3
        
        field_names = [c.field_name for c in document_corrections]
        assert "vendor_name" in field_names
        assert "invoice_date" in field_names
        assert "total_amount" in field_names

    def test_multiple_corrections_same_field(self, db_session: Session, test_user_and_document):
        """Test multiple corrections for the same field (correction history)"""
        user, document = test_user_and_document
        
        # First correction
        correction1 = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="XYZ Corp",
            corrected_value="XYZ Corporation",
            corrected_by=user.id
        )
        db_session.add(correction1)
        db_session.commit()
        db_session.refresh(correction1)
        
        # Second correction of the same field
        correction2 = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="XYZ Corporation",  # Previous corrected value becomes original
            corrected_value="XYZ Corp Ltd.",
            corrected_by=user.id
        )
        db_session.add(correction2)
        db_session.commit()
        db_session.refresh(correction2)
        
        # Query corrections for this field
        vendor_corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id,
            FieldCorrection.field_name == "vendor_name"
        ).order_by(FieldCorrection.timestamp).all()
        
        assert len(vendor_corrections) == 2
        assert vendor_corrections[0].corrected_value == "XYZ Corporation"
        assert vendor_corrections[1].corrected_value == "XYZ Corp Ltd."
        assert vendor_corrections[0].timestamp < vendor_corrections[1].timestamp

    def test_correction_cascade_delete_with_document(self, db_session: Session, test_user_and_document):
        """Test that corrections are deleted when document is deleted"""
        user, document = test_user_and_document
        
        # Create multiple corrections
        corrections = [
            FieldCorrection(
                document_id=document.id,
                field_name="field1",
                original_value="orig1",
                corrected_value="corr1",
                corrected_by=user.id
            ),
            FieldCorrection(
                document_id=document.id,
                field_name="field2",
                original_value="orig2",
                corrected_value="corr2",
                corrected_by=user.id
            )
        ]
        
        for correction in corrections:
            db_session.add(correction)
        db_session.commit()
        
        # Verify corrections exist
        correction_count = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id
        ).count()
        assert correction_count == 2
        
        # Delete document
        db_session.delete(document)
        db_session.commit()
        
        # Verify corrections were cascade deleted
        remaining_corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id
        ).count()
        assert remaining_corrections == 0

    def test_correction_with_extracted_field_context(self, db_session: Session, test_user_and_document):
        """Test correction in context with actual extracted fields"""
        user, document = test_user_and_document
        
        # Create an extracted field
        extracted_field = ExtractedField(
            document_id=document.id,
            field_name="vendor_name",
            value="Original Vendor",
            confidence=0.65  # Low confidence
        )
        db_session.add(extracted_field)
        db_session.commit()
        db_session.refresh(extracted_field)
        
        # Create correction for the same field
        correction = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",  # Same field name as extracted field
            original_value="Original Vendor",  # Same as extracted field value
            corrected_value="Corrected Vendor Name",
            corrected_by=user.id
        )
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)
        
        # Query both extracted field and correction
        document_fields = db_session.query(ExtractedField).filter(
            ExtractedField.document_id == document.id
        ).all()
        
        document_corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id
        ).all()
        
        assert len(document_fields) == 1
        assert len(document_corrections) == 1
        assert document_fields[0].field_name == document_corrections[0].field_name
        assert document_fields[0].value == document_corrections[0].original_value

    def test_corrections_by_different_users(self, db_session: Session):
        """Test corrections made by different users on same document"""
        # Create two users in same business
        user1 = create_user_and_business(
            db=db_session,
            email="user1@testbiz.com",
            password="password123",
            business_name="Test Business"
        )
        
        user2 = User(
            email="user2@testbiz.com",
            password_hash="hashedpassword",
            business_id=user1.business_id
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)
        
        # Create document
        document = Document(
            user_id=user1.id,
            business_id=user1.business_id,
            filename="shared_document.pdf",
            file_url="https://example.com/shared_document.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # User1 makes a correction
        correction1 = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="Vendor ABC",
            corrected_value="ABC Vendor Inc",
            corrected_by=user1.id
        )
        
        # User2 makes a different correction
        correction2 = FieldCorrection(
            document_id=document.id,
            field_name="total_amount",
            original_value="$500.00",
            corrected_value="$550.00",
            corrected_by=user2.id
        )
        
        db_session.add_all([correction1, correction2])
        db_session.commit()
        
        # Verify both corrections exist with correct users
        corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id
        ).all()
        
        assert len(corrections) == 2
        
        user1_corrections = [c for c in corrections if c.corrected_by == user1.id]
        user2_corrections = [c for c in corrections if c.corrected_by == user2.id]
        
        assert len(user1_corrections) == 1
        assert len(user2_corrections) == 1
        assert user1_corrections[0].field_name == "vendor_name"
        assert user2_corrections[0].field_name == "total_amount"