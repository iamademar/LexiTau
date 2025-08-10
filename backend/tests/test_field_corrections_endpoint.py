"""
Tests for field corrections endpoint.
Tests submission of corrections for existing and non-existing fields,
document state validation, and access control.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from decimal import Decimal
from uuid import uuid4

from app.main import app
from app.models import Business, User, Document, ExtractedField, FieldCorrection
from app.enums import DocumentStatus, DocumentType, FileType
from app.auth import create_access_token, create_user_and_business
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
def test_user_and_token(db_session):
    """Create a test user and JWT token"""
    user = create_user_and_business(
        db=db_session,
        email="fieldcorrector@example.com",
        password="testpassword123",
        business_name="Field Correction Business"
    )
    
    token = create_access_token(data={"sub": user.email})
    return user, token


@pytest.fixture
def completed_document_with_fields(db_session, test_user_and_token):
    """Create a completed document with extracted fields"""
    user, token = test_user_and_token
    
    document = Document(
        user_id=user.id,
        business_id=user.business_id,
        filename="test_invoice_corrections.pdf",
        file_url="https://example.com/test_invoice_corrections.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.COMPLETED,
        confidence_score=0.75
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    # Add some extracted fields
    fields = [
        ExtractedField(
            document_id=document.id,
            field_name="vendor_name",
            value="ABC Company",
            confidence=0.85
        ),
        ExtractedField(
            document_id=document.id,
            field_name="invoice_number",
            value="INV-001",
            confidence=0.95
        ),
        ExtractedField(
            document_id=document.id,
            field_name="total_amount",
            value="$500.00",
            confidence=0.65  # Low confidence
        )
    ]
    
    for field in fields:
        db_session.add(field)
    
    db_session.commit()
    
    return document, token


@pytest.fixture
def pending_document(db_session, test_user_and_token):
    """Create a document in PENDING status"""
    user, token = test_user_and_token
    
    document = Document(
        user_id=user.id,
        business_id=user.business_id,
        filename="pending_document.pdf",
        file_url="https://example.com/pending_document.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.PENDING  # Not completed
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    return document, token


class TestFieldCorrectionsEndpoint:
    """Test field corrections endpoint"""
    
    def test_correct_existing_fields(self, db_session: Session, completed_document_with_fields):
        """Test correcting existing fields"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "vendor_name",
                    "corrected_value": "ABC Corporation Inc."
                },
                {
                    "field_name": "total_amount",
                    "corrected_value": "$550.00"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["document_id"] == str(document.id)
        assert data["corrections_applied"] == 2
        assert data["corrections_failed"] == 0
        assert len(data["results"]) == 2
        
        # Check correction results
        results = {r["field_name"]: r for r in data["results"]}
        
        vendor_result = results["vendor_name"]
        assert vendor_result["success"] is True
        assert vendor_result["original_value"] == "ABC Company"
        assert vendor_result["corrected_value"] == "ABC Corporation Inc."
        assert vendor_result["was_new_field"] is False
        
        amount_result = results["total_amount"]
        assert amount_result["success"] is True
        assert amount_result["original_value"] == "$500.00"
        assert amount_result["corrected_value"] == "$550.00"
        assert amount_result["was_new_field"] is False
        
        # Check updated fields in response
        updated_fields = {f["field_name"]: f for f in data["updated_fields"]}
        assert updated_fields["vendor_name"]["value"] == "ABC Corporation Inc."
        assert updated_fields["total_amount"]["value"] == "$550.00"
        assert updated_fields["invoice_number"]["value"] == "INV-001"  # Unchanged
        
        # Verify corrections were logged in database
        corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id
        ).all()
        assert len(corrections) == 2
        
        # Verify fields were updated in database
        updated_vendor = db_session.query(ExtractedField).filter(
            ExtractedField.document_id == document.id,
            ExtractedField.field_name == "vendor_name"
        ).first()
        assert updated_vendor.value == "ABC Corporation Inc."

    def test_correct_non_existing_fields(self, db_session: Session, completed_document_with_fields):
        """Test correcting fields that don't exist (creates new fields)"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "due_date",
                    "corrected_value": "2024-09-01"
                },
                {
                    "field_name": "tax_amount",
                    "corrected_value": "$50.00"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["corrections_applied"] == 2
        assert data["corrections_failed"] == 0
        
        # Check that new fields were created
        results = {r["field_name"]: r for r in data["results"]}
        
        due_date_result = results["due_date"]
        assert due_date_result["success"] is True
        assert due_date_result["original_value"] is None
        assert due_date_result["corrected_value"] == "2024-09-01"
        assert due_date_result["was_new_field"] is True
        
        tax_result = results["tax_amount"]
        assert tax_result["success"] is True
        assert tax_result["original_value"] is None
        assert tax_result["corrected_value"] == "$50.00"
        assert tax_result["was_new_field"] is True
        
        # Verify new fields exist in database
        new_fields = db_session.query(ExtractedField).filter(
            ExtractedField.document_id == document.id,
            ExtractedField.field_name.in_(["due_date", "tax_amount"])
        ).all()
        assert len(new_fields) == 2
        
        field_values = {f.field_name: f.value for f in new_fields}
        assert field_values["due_date"] == "2024-09-01"
        assert field_values["tax_amount"] == "$50.00"
        
        # New fields should have None confidence (user-corrected)
        for field in new_fields:
            assert field.confidence is None

    def test_mixed_existing_and_new_fields(self, db_session: Session, completed_document_with_fields):
        """Test correcting mix of existing and non-existing fields"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "vendor_name",  # Existing field
                    "corrected_value": "Updated Vendor Name"
                },
                {
                    "field_name": "new_field",  # New field
                    "corrected_value": "New Field Value"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["corrections_applied"] == 2
        assert data["corrections_failed"] == 0
        
        results = {r["field_name"]: r for r in data["results"]}
        assert results["vendor_name"]["was_new_field"] is False
        assert results["new_field"]["was_new_field"] is True

    def test_document_not_completed_status(self, db_session: Session, pending_document):
        """Test rejection when document is not in COMPLETED status"""
        document, token = pending_document
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "vendor_name",
                    "corrected_value": "Test Vendor"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "PENDING status" in data["detail"]
        assert "Document must be COMPLETED" in data["detail"]

    def test_document_not_found(self, db_session: Session, test_user_and_token):
        """Test 404 when document doesn't exist"""
        user, token = test_user_and_token
        
        fake_document_id = uuid4()
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "test_field",
                    "corrected_value": "test_value"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{fake_document_id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Document not found or access denied" in data["detail"]

    def test_unauthorized_access(self, db_session: Session, completed_document_with_fields):
        """Test access denied when user doesn't own document"""
        document, original_token = completed_document_with_fields
        
        # Create different user in different business
        other_user = create_user_and_business(
            db=db_session,
            email="otheruser@differentbiz.com",
            password="password123",
            business_name="Different Business"
        )
        other_token = create_access_token(data={"sub": other_user.email})
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "vendor_name",
                    "corrected_value": "Unauthorized Change"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {other_token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Document not found or access denied" in data["detail"]

    def test_empty_corrections_list(self, db_session: Session, completed_document_with_fields):
        """Test validation error for empty corrections list"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": []  # Empty list
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "ensure this value has at least 1 items" in str(data["detail"])

    def test_invalid_field_name(self, db_session: Session, completed_document_with_fields):
        """Test validation error for empty field name"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "",  # Empty field name
                    "corrected_value": "test_value"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "ensure this value has at least 1 characters" in str(data["detail"])

    def test_no_authorization_header(self, db_session: Session, completed_document_with_fields):
        """Test 403 when no authorization header provided"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "test_field",
                    "corrected_value": "test_value"
                }
            ]
        }
        
        # No authorization header
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload
        )
        
        assert response.status_code == 403

    def test_multiple_corrections_same_field(self, db_session: Session, completed_document_with_fields):
        """Test multiple corrections for the same field in one request"""
        document, token = completed_document_with_fields
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "vendor_name",
                    "corrected_value": "First Correction"
                },
                {
                    "field_name": "vendor_name",
                    "corrected_value": "Second Correction"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Both corrections should be applied
        assert data["corrections_applied"] == 2
        assert data["corrections_failed"] == 0
        
        # Final value should be the last correction
        updated_fields = {f["field_name"]: f for f in data["updated_fields"]}
        assert updated_fields["vendor_name"]["value"] == "Second Correction"
        
        # Both corrections should be logged
        corrections = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id,
            FieldCorrection.field_name == "vendor_name"
        ).all()
        assert len(corrections) == 2

    def test_correction_audit_trail(self, db_session: Session, completed_document_with_fields):
        """Test that corrections are properly logged in audit trail"""
        document, token = completed_document_with_fields
        user = db_session.query(User).filter(User.email == "fieldcorrector@example.com").first()
        
        corrections_payload = {
            "corrections": [
                {
                    "field_name": "vendor_name",
                    "corrected_value": "Audited Correction"
                }
            ]
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/documents/{document.id}/fields/correct",
            json=corrections_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Verify correction is logged
        correction = db_session.query(FieldCorrection).filter(
            FieldCorrection.document_id == document.id,
            FieldCorrection.field_name == "vendor_name"
        ).first()
        
        assert correction is not None
        assert correction.original_value == "ABC Company"
        assert correction.corrected_value == "Audited Correction"
        assert correction.corrected_by == user.id
        assert correction.timestamp is not None

    def test_different_document_statuses(self, db_session: Session, test_user_and_token):
        """Test corrections rejected for different document statuses"""
        user, token = test_user_and_token
        
        statuses_to_test = [
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.FAILED
        ]
        
        for status in statuses_to_test:
            document = Document(
                user_id=user.id,
                business_id=user.business_id,
                filename=f"test_{status.value}.pdf",
                file_url=f"https://example.com/test_{status.value}.pdf",
                file_type=FileType.PDF,
                document_type=DocumentType.INVOICE,
                status=status
            )
            db_session.add(document)
            db_session.commit()
            db_session.refresh(document)
            
            corrections_payload = {
                "corrections": [
                    {
                        "field_name": "test_field",
                        "corrected_value": "test_value"
                    }
                ]
            }
            
            headers = {"Authorization": f"Bearer {token}"}
            response = client.post(
                f"/documents/{document.id}/fields/correct",
                json=corrections_payload,
                headers=headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert f"document in {status.value} status" in data["detail"]
            assert "Document must be COMPLETED" in data["detail"]