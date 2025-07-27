import pytest
import uuid
from sqlalchemy.orm import Session
from app.models import Document, User, Business
from app.enums import FileType, DocumentType, DocumentStatus
from app.auth import create_user_and_business
from app.test_db import create_test_tables, drop_test_tables, get_test_db


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
        db.query(Document).delete()
        db.query(User).delete()
        db.query(Business).delete()
        db.commit()
        db.close()


@pytest.fixture
def test_user_and_business(db_session):
    """Create a test user and business for document tests"""
    user = create_user_and_business(
        db=db_session,
        email="testuser@example.com",
        password="testpassword123",
        business_name="Test Business"
    )
    return user, user.business


def test_create_document(db_session: Session, test_user_and_business):
    """Test creating a new document"""
    user, business = test_user_and_business
    
    # Create a new document
    document = Document(
        user_id=user.id,
        business_id=business.id,
        filename="test_invoice.pdf",
        file_url="https://example.com/files/test_invoice.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.PENDING,
        confidence_score=0.95
    )
    
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    # Verify the document was created correctly
    assert document.id is not None
    assert isinstance(document.id, uuid.UUID)
    assert document.user_id == user.id
    assert document.business_id == business.id
    assert document.filename == "test_invoice.pdf"
    assert document.file_url == "https://example.com/files/test_invoice.pdf"
    assert document.file_type == FileType.PDF
    assert document.document_type == DocumentType.INVOICE
    assert document.status == DocumentStatus.PENDING
    assert document.confidence_score == 0.95
    assert document.created_at is not None
    assert document.updated_at is None


def test_document_relationships(db_session: Session, test_user_and_business):
    """Test document relationships with user and business"""
    user, business = test_user_and_business
    
    # Create a document
    document = Document(
        user_id=user.id,
        business_id=business.id,
        filename="test_receipt.jpg",
        file_url="https://example.com/files/test_receipt.jpg",
        file_type=FileType.JPG,
        document_type=DocumentType.RECEIPT,
        status=DocumentStatus.PROCESSING
    )
    
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    # Test relationships
    assert document.user.id == user.id
    assert document.user.email == user.email
    assert document.business.id == business.id
    assert document.business.name == business.name
    
    # Test reverse relationship
    assert document in user.documents


def test_document_enums(db_session: Session, test_user_and_business):
    """Test all enum values work correctly"""
    user, business = test_user_and_business
    
    # Test PDF document
    pdf_doc = Document(
        user_id=user.id,
        business_id=business.id,
        filename="document.pdf",
        file_url="https://example.com/document.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.PENDING
    )
    
    # Test JPG document
    jpg_doc = Document(
        user_id=user.id,
        business_id=business.id,
        filename="receipt.jpg",
        file_url="https://example.com/receipt.jpg",
        file_type=FileType.JPG,
        document_type=DocumentType.RECEIPT,
        status=DocumentStatus.PROCESSING
    )
    
    # Test PNG document
    png_doc = Document(
        user_id=user.id,
        business_id=business.id,
        filename="scan.png",
        file_url="https://example.com/scan.png",
        file_type=FileType.PNG,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.COMPLETED
    )
    
    db_session.add_all([pdf_doc, jpg_doc, png_doc])
    db_session.commit()
    
    # Query and verify enum values
    docs = db_session.query(Document).all()
    assert len(docs) == 3
    
    file_types = {doc.file_type for doc in docs}
    assert file_types == {FileType.PDF, FileType.JPG, FileType.PNG}
    
    doc_types = {doc.document_type for doc in docs}
    assert doc_types == {DocumentType.INVOICE, DocumentType.RECEIPT}
    
    statuses = {doc.status for doc in docs}
    assert statuses == {DocumentStatus.PENDING, DocumentStatus.PROCESSING, DocumentStatus.COMPLETED}


def test_document_query_by_status(db_session: Session, test_user_and_business):
    """Test querying documents by status"""
    user, business = test_user_and_business
    
    # Create documents with different statuses
    pending_doc = Document(
        user_id=user.id,
        business_id=business.id,
        filename="pending.pdf",
        file_url="https://example.com/pending.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.PENDING
    )
    
    completed_doc = Document(
        user_id=user.id,
        business_id=business.id,
        filename="completed.pdf",
        file_url="https://example.com/completed.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.COMPLETED
    )
    
    failed_doc = Document(
        user_id=user.id,
        business_id=business.id,
        filename="failed.pdf",
        file_url="https://example.com/failed.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.FAILED
    )
    
    db_session.add_all([pending_doc, completed_doc, failed_doc])
    db_session.commit()
    
    # Query by status
    pending_docs = db_session.query(Document).filter(Document.status == DocumentStatus.PENDING).all()
    completed_docs = db_session.query(Document).filter(Document.status == DocumentStatus.COMPLETED).all()
    failed_docs = db_session.query(Document).filter(Document.status == DocumentStatus.FAILED).all()
    
    assert len(pending_docs) == 1
    assert len(completed_docs) == 1
    assert len(failed_docs) == 1
    assert pending_docs[0].filename == "pending.pdf"
    assert completed_docs[0].filename == "completed.pdf"
    assert failed_docs[0].filename == "failed.pdf"


def test_document_query_by_user(db_session: Session, test_user_and_business):
    """Test querying documents by user"""
    user, business = test_user_and_business
    
    # Create another user for testing
    user2 = create_user_and_business(
        db=db_session,
        email="user2@example.com",
        password="password123",
        business_name="Business 2"
    )
    
    # Create documents for both users
    doc1 = Document(
        user_id=user.id,
        business_id=business.id,
        filename="user1_doc.pdf",
        file_url="https://example.com/user1_doc.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.PENDING
    )
    
    doc2 = Document(
        user_id=user2.id,
        business_id=user2.business_id,
        filename="user2_doc.pdf",
        file_url="https://example.com/user2_doc.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.RECEIPT,
        status=DocumentStatus.COMPLETED
    )
    
    db_session.add_all([doc1, doc2])
    db_session.commit()
    
    # Query documents by user
    user1_docs = db_session.query(Document).filter(Document.user_id == user.id).all()
    user2_docs = db_session.query(Document).filter(Document.user_id == user2.id).all()
    
    assert len(user1_docs) == 1
    assert len(user2_docs) == 1
    assert user1_docs[0].filename == "user1_doc.pdf"
    assert user2_docs[0].filename == "user2_doc.pdf"


def test_document_uuid_uniqueness(db_session: Session, test_user_and_business):
    """Test that document UUIDs are unique"""
    user, business = test_user_and_business
    
    # Create multiple documents
    docs = []
    for i in range(5):
        doc = Document(
            user_id=user.id,
            business_id=business.id,
            filename=f"doc_{i}.pdf",
            file_url=f"https://example.com/doc_{i}.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.PENDING
        )
        docs.append(doc)
    
    db_session.add_all(docs)
    db_session.commit()
    
    # Verify all UUIDs are unique
    doc_ids = [doc.id for doc in docs]
    assert len(set(doc_ids)) == len(doc_ids)  # All IDs should be unique
    assert all(isinstance(doc_id, uuid.UUID) for doc_id in doc_ids)