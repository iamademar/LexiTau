import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Business, User, Document
from app.enums import DocumentType, DocumentStatus, DocumentClassification, FileType
import uuid


class TestDocument:
    def test_create_document_with_required_fields(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            business_id=business.id
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        document = Document(
            user_id=user.id,
            business_id=business.id,
            filename="test_invoice.pdf",
            file_url="https://blob.url",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.REVENUE,
            status=DocumentStatus.PENDING
        )
        test_db.add(document)
        test_db.commit()
        test_db.refresh(document)
        
        assert document.id is not None
        assert document.user_id == user.id
        assert document.business_id == business.id
        assert document.filename == "test_invoice.pdf"
        assert document.file_url == "https://blob.url"
        assert document.file_type == FileType.PDF
        assert document.document_type == DocumentType.INVOICE
        assert document.classification == DocumentClassification.REVENUE
        assert document.status == DocumentStatus.PENDING
        assert document.created_at is not None

    def test_document_classification_required(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        user = User(
            email="test@example.com",
            password_hash="password",
            business_id=business.id
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        with pytest.raises(IntegrityError):
            document = Document(
                user_id=user.id,
                business_id=business.id,
                filename="test.pdf",
                file_url="https://blob.url",
                file_type=FileType.PDF,
                document_type=DocumentType.INVOICE,
                status=DocumentStatus.PENDING
            )
            test_db.add(document)
            test_db.commit()

    def test_document_import_and_instantiation(self):
        """Test that Document model can be imported and instantiated with minimal fields (no DB commit)"""
        document = Document(
            user_id=1,
            business_id=1,
            filename="test.pdf",
            file_url="https://blob.url",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            classification=DocumentClassification.REVENUE,
            status=DocumentStatus.PENDING
        )
        
        assert document.user_id == 1
        assert document.business_id == 1
        assert document.filename == "test.pdf"
        assert document.file_type == FileType.PDF
        assert document.document_type == DocumentType.INVOICE
        assert document.classification == DocumentClassification.REVENUE
        assert document.status == DocumentStatus.PENDING
        assert document.__class__.__name__ == "Document"