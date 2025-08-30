"""
Tests for FieldCorrection model functionality.
Tests correction creation, relationships, and data integrity.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from app.main import app
from app.models import Business, User, Document, ExtractedField, FieldCorrection
from app.enums import DocumentStatus, DocumentType, FileType, DocumentClassification
from app.auth import create_user_and_business
from app.db import get_db


# IMPORTANT: do NOT create TestClient or override get_db at import time.
# Make a client fixture that yields the SAME SQLite session as db_session.
@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_and_document(db_session: Session):
    """Create a test user and document for correction tests"""
    user = create_user_and_business(
        db=db_session,
        email="corrector@example.com",
        password="testpassword123",
        business_name="Correction Test Business",
    )

    document = Document(
        user_id=user.id,
        business_id=user.business_id,
        filename="test_invoice.pdf",
        file_url="https://example.com/test_invoice.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        classification=DocumentClassification.EXPENSE,
        status=DocumentStatus.COMPLETED,
        confidence_score=0.85,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return user, document


class TestFieldCorrectionModel:
    def test_field_correction_creation(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document
        correction = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="Acme Corp",
            corrected_value="ACME Corporation",
            corrected_by=user.id,
        )
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)

        assert correction.id is not None
        assert correction.document_id == document.id
        assert correction.field_name == "vendor_name"
        assert correction.original_value == "Acme Corp"
        assert correction.corrected_value == "ACME Corporation"
        assert correction.corrected_by == user.id
        assert isinstance(correction.timestamp, datetime)

    def test_field_correction_with_null_original_value(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document
        correction = FieldCorrection(
            document_id=document.id,
            field_name="invoice_number",
            original_value=None,
            corrected_value="INV-2024-001",
            corrected_by=user.id,
        )
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)

        assert correction.original_value is None
        assert correction.corrected_value == "INV-2024-001"

    def test_field_correction_relationships(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document
        correction = FieldCorrection(
            document_id=document.id,
            field_name="total_amount",
            original_value="$100.00",
            corrected_value="$150.00",
            corrected_by=user.id,
        )
        db_session.add(correction)
        db_session.commit()
        db_session.refresh(correction)

        assert correction.document is not None
        assert correction.document.id == document.id
        assert correction.document.filename == "test_invoice.pdf"

        assert correction.corrected_by_user is not None
        assert correction.corrected_by_user.id == user.id
        assert correction.corrected_by_user.email == "corrector@example.com"

        assert len(document.field_corrections) == 1
        assert document.field_corrections[0].id == correction.id

        assert len(user.field_corrections) == 1
        assert user.field_corrections[0].id == correction.id

    def test_multiple_corrections_for_document(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document
        data = [
            {"field_name": "vendor_name",  "original_value": "ABC Inc",     "corrected_value": "ABC Incorporated"},
            {"field_name": "invoice_date", "original_value": "2024-01-01",  "corrected_value": "2024-01-15"},
            {"field_name": "total_amount", "original_value": "$999.99",     "corrected_value": "$1,099.99"},
        ]
        created = []
        for d in data:
            c = FieldCorrection(document_id=document.id, corrected_by=user.id, **d)
            db_session.add(c)
            created.append(c)
        db_session.commit()
        for c in created:
            db_session.refresh(c)

        rows = db_session.query(FieldCorrection).filter(FieldCorrection.document_id == document.id).all()
        assert len(rows) == 3
        names = [c.field_name for c in rows]
        assert "vendor_name" in names and "invoice_date" in names and "total_amount" in names

    def test_multiple_corrections_same_field(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document

        # First correction
        c1 = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="XYZ Corp",
            corrected_value="XYZ Corporation",
            corrected_by=user.id,
        )
        db_session.add(c1); db_session.commit(); db_session.refresh(c1)

        # Second correction (same field)
        c2 = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="XYZ Corporation",
            corrected_value="XYZ Corp Ltd.",
            corrected_by=user.id,
        )
        db_session.add(c2); db_session.commit(); db_session.refresh(c2)

        # Stable ordering; UUID tie-breaker means order isn't guaranteed across runs
        vendor_corr = (
            db_session.query(FieldCorrection)
            .filter(
                FieldCorrection.document_id == document.id,
                FieldCorrection.field_name == "vendor_name",
            )
            .order_by(FieldCorrection.timestamp, FieldCorrection.id)
            .all()
        )

        # Assert both corrections exist (order-agnostic)
        assert len(vendor_corr) == 2
        assert {vc.corrected_value for vc in vendor_corr} == {"XYZ Corporation", "XYZ Corp Ltd."}

        # Allow same-second ties on SQLite; ensure non-decreasing timestamps
        assert vendor_corr[0].timestamp <= vendor_corr[1].timestamp


    def test_correction_cascade_delete_with_document(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document

        db_session.add_all(
            [
                FieldCorrection(document_id=document.id, field_name="field1", original_value="orig1", corrected_value="corr1", corrected_by=user.id),
                FieldCorrection(document_id=document.id, field_name="field2", original_value="orig2", corrected_value="corr2", corrected_by=user.id),
            ]
        )
        db_session.commit()

        assert db_session.query(FieldCorrection).filter(FieldCorrection.document_id == document.id).count() == 2

        db_session.delete(document)
        db_session.commit()

        assert db_session.query(FieldCorrection).filter(FieldCorrection.document_id == document.id).count() == 0

    def test_correction_with_extracted_field_context(self, db_session: Session, test_user_and_document):
        user, document = test_user_and_document

        ef = ExtractedField(
            document_id=document.id,
            field_name="vendor_name",
            value="Original Vendor",
            confidence=0.65,
        )
        db_session.add(ef); db_session.commit(); db_session.refresh(ef)

        corr = FieldCorrection(
            document_id=document.id,
            field_name="vendor_name",
            original_value="Original Vendor",
            corrected_value="Corrected Vendor Name",
            corrected_by=user.id,
        )
        db_session.add(corr); db_session.commit(); db_session.refresh(corr)

        fields = db_session.query(ExtractedField).filter(ExtractedField.document_id == document.id).all()
        corrs = db_session.query(FieldCorrection).filter(FieldCorrection.document_id == document.id).all()
        assert len(fields) == 1 and len(corrs) == 1
        assert fields[0].field_name == corrs[0].field_name
        assert fields[0].value == corrs[0].original_value

    def test_corrections_by_different_users(self, db_session: Session):
        user1 = create_user_and_business(
            db=db_session, email="user1@testbiz.com", password="password123", business_name="Test Business"
        )

        user2 = User(email="user2@testbiz.com", password_hash="hashedpassword", business_id=user1.business_id)
        db_session.add(user2); db_session.commit(); db_session.refresh(user2)

        document = Document(
            user_id=user1.id,
            business_id=user1.business_id,
            filename="shared_document.pdf",
            file_url="https://example.com/shared_document.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.EXPENSE,
            status=DocumentStatus.COMPLETED,
        )
        db_session.add(document); db_session.commit(); db_session.refresh(document)

        c1 = FieldCorrection(
            document_id=document.id, field_name="vendor_name",
            original_value="Vendor ABC", corrected_value="ABC Vendor Inc", corrected_by=user1.id
        )
        c2 = FieldCorrection(
            document_id=document.id, field_name="total_amount",
            original_value="$500.00", corrected_value="$550.00", corrected_by=user2.id
        )
        db_session.add_all([c1, c2]); db_session.commit()

        corrs = db_session.query(FieldCorrection).filter(FieldCorrection.document_id == document.id).all()
        assert len(corrs) == 2
        assert any(c.corrected_by == user1.id and c.field_name == "vendor_name" for c in corrs)
        assert any(c.corrected_by == user2.id and c.field_name == "total_amount" for c in corrs)
