import pytest
import io
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import User, Business, Document
from app.auth import create_user_and_business, create_access_token
from app.test_db import get_test_db, create_test_tables, drop_test_tables
from app.enums import DocumentStatus, FileType, DocumentType


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
def test_user_and_token(db_session):
    """Create a test user and JWT token"""
    user = create_user_and_business(
        db=db_session,
        email="testuser@example.com",
        password="testpassword123",
        business_name="Test Business"
    )
    
    # Create JWT token
    token = create_access_token(data={"sub": user.email})
    
    return user, token


@pytest.fixture
def client(db_session):
    """Create test client with dependency overrides"""
    from app.db import get_db
    from app.test_db import get_test_db
    
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestClient(app)
    
    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(test_user_and_token):
    """Get authorization headers with JWT token"""
    user, token = test_user_and_token
    return {"Authorization": f"Bearer {token}"}


def create_test_file(filename: str, content: bytes = b"test content", content_type: str = "application/pdf") -> UploadFile:
    """Create a test UploadFile object"""
    file_like = io.BytesIO(content)
    upload_file = UploadFile(filename=filename, file=file_like)
    upload_file.content_type = content_type
    return upload_file


class TestDocumentUpload:
    """Test cases for document upload endpoint"""
    
    @patch('app.routers.documents.get_azure_blob_service')
    def test_upload_single_valid_file(self, mock_get_service, client, auth_headers, db_session):
        """Test uploading a single valid PDF file"""
        # Mock Azure service
        mock_service = mock_get_service.return_value
        mock_service.validate_file_type.return_value = True
        
        # Create async mock for upload_file
        async def mock_upload_file(*args, **kwargs):
            return "https://storage.blob.core.windows.net/test/file.pdf"
        
        mock_service.upload_file = AsyncMock(return_value="https://storage.blob.core.windows.net/test/file.pdf")
        
        # Create test file
        test_content = b"fake PDF content"
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files={"files": ("test_document.pdf", test_content, "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_files"] == 1
        assert data["successful_uploads"] == 1
        assert data["failed_uploads"] == 0
        assert len(data["results"]) == 1
        
        result = data["results"][0]
        assert result["success"] is True
        assert result["filename"] == "test_document.pdf"
        assert result["document_id"] is not None
        assert result["blob_url"] == "https://storage.blob.core.windows.net/test/file.pdf"
    
    @patch('app.routers.documents.get_azure_blob_service')
    def test_upload_invalid_file_type(self, mock_get_service, client, auth_headers):
        """Test uploading an invalid file type"""
        mock_service = mock_get_service.return_value
        mock_service.validate_file_type.return_value = False
        
        test_content = b"text file content"
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files={"files": ("test_document.txt", test_content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_files"] == 1
        assert data["successful_uploads"] == 0
        assert data["failed_uploads"] == 1
        
        result = data["results"][0]
        assert result["success"] is False
        assert result["filename"] == "test_document.txt"
        assert "Invalid file type" in result["error_message"]
    
    @patch('app.routers.documents.get_azure_blob_service')
    def test_upload_multiple_mixed_files(self, mock_get_service, client, auth_headers):
        """Test uploading multiple files with mixed validity"""
        # Mock Azure service
        mock_service = mock_get_service.return_value
        
        # Mock responses for different files
        def validate_side_effect(file):
            return file.filename.endswith('.pdf')
        
        mock_service.validate_file_type.side_effect = validate_side_effect
        mock_service.upload_file = AsyncMock(return_value="https://storage.blob.core.windows.net/test/file.pdf")
        
        files = [
            ("files", ("valid_document.pdf", b"PDF content", "application/pdf")),
            ("files", ("invalid_document.txt", b"Text content", "text/plain"))
        ]
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_files"] == 2
        assert data["successful_uploads"] == 1
        assert data["failed_uploads"] == 1
        
        # Check individual results
        results = {r["filename"]: r for r in data["results"]}
        
        assert results["valid_document.pdf"]["success"] is True
        assert results["invalid_document.txt"]["success"] is False
        assert "Invalid file type" in results["invalid_document.txt"]["error_message"]
    
    def test_upload_without_authentication(self, client):
        """Test uploading without JWT token"""
        response = client.post(
            "/documents/upload",
            files={"files": ("test.pdf", b"content", "application/pdf")}
        )
        
        assert response.status_code == 403
    
    def test_upload_with_invalid_token(self, client):
        """Test uploading with invalid JWT token"""
        headers = {"Authorization": "Bearer invalid-token"}
        
        response = client.post(
            "/documents/upload",
            headers=headers,
            files={"files": ("test.pdf", b"content", "application/pdf")}
        )
        
        assert response.status_code == 401
    
    def test_upload_no_files(self, client, auth_headers):
        """Test uploading with no files"""
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files={}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_upload_too_many_files(self, client, auth_headers):
        """Test uploading more than 10 files"""
        files = [
            ("files", (f"file_{i}.pdf", b"content", "application/pdf"))
            for i in range(12)  # More than 10 files
        ]
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400
        assert "Too many files" in response.json()["detail"]
    
    @patch('app.routers.documents.validate_file_size')
    @patch('app.routers.documents.get_file_size')
    @patch('app.routers.documents.get_azure_blob_service')
    def test_upload_file_size_limit(self, mock_get_service, mock_get_size, mock_validate_size, client, auth_headers):
        """Test file size validation"""
        mock_service = mock_get_service.return_value
        mock_service.validate_file_type.return_value = True
        mock_service.upload_file = AsyncMock(return_value="https://storage.blob.core.windows.net/test/file.pdf")
        mock_get_size.return_value = 11 * 1024 * 1024  # 11MB (over limit)
        mock_validate_size.return_value = False  # File size validation fails
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files={"files": ("large_file.pdf", b"content", "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["failed_uploads"] == 1
        result = data["results"][0]
        assert result["success"] is False
        assert "exceeds limit" in result["error_message"]
    
    @patch('app.routers.documents.dispatch_ocr_task')
    @patch('app.routers.documents.get_azure_blob_service')
    def test_document_status_update_after_queueing(self, mock_get_service, mock_dispatch_task, client, auth_headers, db_session):
        """Test that document status is updated to PROCESSING after successful task queueing"""
        # Mock Azure service
        mock_service = mock_get_service.return_value
        mock_service.validate_file_type.return_value = True
        mock_service.upload_file = AsyncMock(return_value="https://storage.blob.core.windows.net/test/file.pdf")
        
        # Mock Celery task dispatch to return a task ID
        mock_dispatch_task.return_value = "task-123-456"
        
        # Create test file
        test_content = b"fake PDF content"
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files={"files": ("test_document.pdf", test_content, "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify API response
        assert data["total_files"] == 1
        assert data["successful_uploads"] == 1
        assert data["failed_uploads"] == 0
        
        result = data["results"][0]
        assert result["success"] is True
        assert result["document_id"] is not None
        
        # Verify that dispatch_ocr_task was called
        mock_dispatch_task.assert_called_once()
        
        # Verify document status in database
        document = db_session.query(Document).filter(
            Document.id == result["document_id"]
        ).first()
        
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING  # Should be PROCESSING after queueing
        assert document.filename == "test_document.pdf"
        assert document.file_url == "https://storage.blob.core.windows.net/test/file.pdf"
    
    @patch('app.routers.documents.dispatch_ocr_task')
    @patch('app.routers.documents.get_azure_blob_service')
    def test_document_status_remains_pending_on_task_failure(self, mock_get_service, mock_dispatch_task, client, auth_headers, db_session):
        """Test that document status remains PENDING if task dispatch fails"""
        # Mock Azure service
        mock_service = mock_get_service.return_value
        mock_service.validate_file_type.return_value = True
        mock_service.upload_file = AsyncMock(return_value="https://storage.blob.core.windows.net/test/file.pdf")
        
        # Mock Celery task dispatch to raise an exception
        mock_dispatch_task.side_effect = Exception("Task dispatch failed")
        
        # Create test file
        test_content = b"fake PDF content"
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files={"files": ("test_document.pdf", test_content, "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have failed upload due to task dispatch error
        assert data["total_files"] == 1
        assert data["successful_uploads"] == 0
        assert data["failed_uploads"] == 1
        
        result = data["results"][0]
        assert result["success"] is False
        assert "Upload failed" in result["error_message"]
    
    @patch('app.routers.documents.dispatch_ocr_task')
    @patch('app.routers.documents.get_azure_blob_service')
    def test_multiple_documents_status_updates(self, mock_get_service, mock_dispatch_task, client, auth_headers, db_session):
        """Test that multiple documents get correct status updates"""
        # Mock Azure service
        mock_service = mock_get_service.return_value
        mock_service.validate_file_type.return_value = True
        mock_service.upload_file = AsyncMock(return_value="https://storage.blob.core.windows.net/test/file.pdf")
        
        # Mock Celery task dispatch to return different task IDs
        mock_dispatch_task.side_effect = ["task-123", "task-456", "task-789"]
        
        files = [
            ("files", ("doc1.pdf", b"PDF content 1", "application/pdf")),
            ("files", ("doc2.pdf", b"PDF content 2", "application/pdf")),
            ("files", ("doc3.pdf", b"PDF content 3", "application/pdf"))
        ]
        
        response = client.post(
            "/documents/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_files"] == 3
        assert data["successful_uploads"] == 3
        assert data["failed_uploads"] == 0
        
        # Verify that dispatch_ocr_task was called 3 times
        assert mock_dispatch_task.call_count == 3
        
        # Verify all documents have PROCESSING status
        for result in data["results"]:
            assert result["success"] is True
            document = db_session.query(Document).filter(
                Document.id == result["document_id"]
            ).first()
            assert document.status == DocumentStatus.PROCESSING


class TestDocumentList:
    """Test cases for listing business documents"""
    
    def test_list_business_documents_basic(self, client, auth_headers, test_user_and_token, db_session):
        """Test basic listing of documents for business"""
        user, token = test_user_and_token
        
        # Create test documents
        doc1 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="doc1.pdf",
            file_url="https://example.com/doc1.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.PENDING
        )
        doc2 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="doc2.jpg",
            file_url="https://example.com/doc2.jpg",
            file_type=FileType.JPG,
            document_type=DocumentType.RECEIPT,
            status=DocumentStatus.COMPLETED
        )
        
        db_session.add_all([doc1, doc2])
        db_session.commit()
        
        response = client.get("/documents/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check pagination structure
        assert "documents" in data
        assert "pagination" in data
        
        documents = data["documents"]
        pagination = data["pagination"]
        
        assert len(documents) == 2
        assert pagination["total_items"] == 2
        assert pagination["page"] == 1
        assert pagination["per_page"] == 20
        assert pagination["total_pages"] == 1
        assert pagination["has_next"] is False
        assert pagination["has_prev"] is False
        
        # Check document data
        filenames = {doc["filename"] for doc in documents}
        assert filenames == {"doc1.pdf", "doc2.jpg"}
    
    def test_filter_by_status(self, client, auth_headers, test_user_and_token, db_session):
        """Test filtering documents by status"""
        user, token = test_user_and_token
        
        # Create documents with different statuses
        doc1 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="pending_doc.pdf",
            file_url="https://example.com/pending.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.PENDING
        )
        doc2 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="processing_doc.pdf",
            file_url="https://example.com/processing.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.PROCESSING
        )
        doc3 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="completed_doc.pdf",
            file_url="https://example.com/completed.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.COMPLETED
        )
        
        db_session.add_all([doc1, doc2, doc3])
        db_session.commit()
        
        # Test filtering by PENDING status
        response = client.get("/documents/?status=PENDING", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "pending_doc.pdf"
        assert data["documents"][0]["status"] == "PENDING"
        assert data["pagination"]["total_items"] == 1
        
        # Test filtering by PROCESSING status
        response = client.get("/documents/?status=PROCESSING", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "processing_doc.pdf"
        assert data["documents"][0]["status"] == "PROCESSING"
        
        # Test filtering by COMPLETED status
        response = client.get("/documents/?status=COMPLETED", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "completed_doc.pdf"
        assert data["documents"][0]["status"] == "COMPLETED"
    
    def test_filter_by_document_type(self, client, auth_headers, test_user_and_token, db_session):
        """Test filtering documents by document type"""
        user, token = test_user_and_token
        
        # Create documents with different types
        doc1 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="invoice1.pdf",
            file_url="https://example.com/invoice1.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.COMPLETED
        )
        doc2 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="invoice2.pdf",
            file_url="https://example.com/invoice2.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.PENDING
        )
        doc3 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="receipt1.jpg",
            file_url="https://example.com/receipt1.jpg",
            file_type=FileType.JPG,
            document_type=DocumentType.RECEIPT,
            status=DocumentStatus.COMPLETED
        )
        
        db_session.add_all([doc1, doc2, doc3])
        db_session.commit()
        
        # Test filtering by INVOICE type
        response = client.get("/documents/?document_type=INVOICE", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 2
        invoice_filenames = {doc["filename"] for doc in data["documents"]}
        assert invoice_filenames == {"invoice1.pdf", "invoice2.pdf"}
        assert all(doc["document_type"] == "INVOICE" for doc in data["documents"])
        assert data["pagination"]["total_items"] == 2
        
        # Test filtering by RECEIPT type
        response = client.get("/documents/?document_type=RECEIPT", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "receipt1.jpg"
        assert data["documents"][0]["document_type"] == "RECEIPT"
        assert data["pagination"]["total_items"] == 1
    
    def test_combined_filters(self, client, auth_headers, test_user_and_token, db_session):
        """Test using multiple filters together"""
        user, token = test_user_and_token
        
        # Create documents with various combinations
        documents = [
            Document(
                user_id=user.id, business_id=user.business_id,
                filename="pending_invoice.pdf", file_url="https://example.com/1.pdf",
                file_type=FileType.PDF, document_type=DocumentType.INVOICE,
                status=DocumentStatus.PENDING
            ),
            Document(
                user_id=user.id, business_id=user.business_id,
                filename="completed_invoice.pdf", file_url="https://example.com/2.pdf",
                file_type=FileType.PDF, document_type=DocumentType.INVOICE,
                status=DocumentStatus.COMPLETED
            ),
            Document(
                user_id=user.id, business_id=user.business_id,
                filename="pending_receipt.jpg", file_url="https://example.com/3.jpg",
                file_type=FileType.JPG, document_type=DocumentType.RECEIPT,
                status=DocumentStatus.PENDING
            ),
            Document(
                user_id=user.id, business_id=user.business_id,
                filename="completed_receipt.jpg", file_url="https://example.com/4.jpg",
                file_type=FileType.JPG, document_type=DocumentType.RECEIPT,
                status=DocumentStatus.COMPLETED
            )
        ]
        
        db_session.add_all(documents)
        db_session.commit()
        
        # Test filtering by both status and document_type
        response = client.get("/documents/?status=PENDING&document_type=INVOICE", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "pending_invoice.pdf"
        assert data["documents"][0]["status"] == "PENDING"
        assert data["documents"][0]["document_type"] == "INVOICE"
        assert data["pagination"]["total_items"] == 1
        
        # Test another combination
        response = client.get("/documents/?status=COMPLETED&document_type=RECEIPT", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "completed_receipt.jpg"
        assert data["documents"][0]["status"] == "COMPLETED"
        assert data["documents"][0]["document_type"] == "RECEIPT"
    
    def test_pagination(self, client, auth_headers, test_user_and_token, db_session):
        """Test pagination functionality"""
        user, token = test_user_and_token
        
        # Create 25 test documents
        documents = []
        for i in range(25):
            doc = Document(
                user_id=user.id,
                business_id=user.business_id,
                filename=f"doc_{i:02d}.pdf",
                file_url=f"https://example.com/doc_{i}.pdf",
                file_type=FileType.PDF,
                document_type=DocumentType.INVOICE,
                status=DocumentStatus.COMPLETED
            )
            documents.append(doc)
        
        db_session.add_all(documents)
        db_session.commit()
        
        # Test first page with default per_page (20)
        response = client.get("/documents/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 20
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 20
        assert data["pagination"]["total_items"] == 25
        assert data["pagination"]["total_pages"] == 2
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False
        
        # Test second page
        response = client.get("/documents/?page=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 5  # Remaining items
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 20
        assert data["pagination"]["total_items"] == 25
        assert data["pagination"]["total_pages"] == 2
        assert data["pagination"]["has_next"] is False
        assert data["pagination"]["has_prev"] is True
        
        # Test custom per_page
        response = client.get("/documents/?per_page=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 10
        assert data["pagination"]["per_page"] == 10
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["has_next"] is True
    
    def test_empty_result(self, client, auth_headers, test_user_and_token, db_session):
        """Test response when no documents match filters"""
        user, token = test_user_and_token
        
        # Create one document
        doc = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="invoice.pdf",
            file_url="https://example.com/invoice.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.COMPLETED
        )
        db_session.add(doc)
        db_session.commit()
        
        # Filter for non-existent status
        response = client.get("/documents/?status=FAILED", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 0
        assert data["pagination"]["total_items"] == 0
        assert data["pagination"]["total_pages"] == 0
        assert data["pagination"]["has_next"] is False
        assert data["pagination"]["has_prev"] is False
    
    def test_business_isolation(self, client, db_session):
        """Test that users only see documents from their own business"""
        from app.auth import create_user_and_business, create_access_token
        
        # Create two different businesses with users
        user1 = create_user_and_business(
            db=db_session,
            email="user1@business1.com",
            password="testpass123",
            business_name="Business 1"
        )
        
        user2 = create_user_and_business(
            db=db_session,
            email="user2@business2.com", 
            password="testpass123",
            business_name="Business 2"
        )
        
        # Create documents for each business
        doc1 = Document(
            user_id=user1.id,
            business_id=user1.business_id,
            filename="business1_doc.pdf",
            file_url="https://example.com/b1_doc.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.COMPLETED
        )
        
        doc2 = Document(
            user_id=user2.id,
            business_id=user2.business_id,
            filename="business2_doc.pdf",
            file_url="https://example.com/b2_doc.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.COMPLETED
        )
        
        db_session.add_all([doc1, doc2])
        db_session.commit()
        
        # Test user1 can only see their business documents
        token1 = create_access_token(data={"sub": user1.email})
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        response = client.get("/documents/", headers=headers1)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "business1_doc.pdf"
        assert data["documents"][0]["business_id"] == user1.business_id
        
        # Test user2 can only see their business documents
        token2 = create_access_token(data={"sub": user2.email})
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        response = client.get("/documents/", headers=headers2)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "business2_doc.pdf"
        assert data["documents"][0]["business_id"] == user2.business_id
    
    def test_list_documents_without_auth(self, client):
        """Test listing documents without authentication"""
        response = client.get("/documents/")
        assert response.status_code == 403
        
    def test_invalid_filter_values(self, client, auth_headers):
        """Test handling of invalid filter values"""
        # Test invalid status
        response = client.get("/documents/?status=INVALID_STATUS", headers=auth_headers)
        assert response.status_code == 422  # Validation error
        
        # Test invalid document_type
        response = client.get("/documents/?document_type=INVALID_TYPE", headers=auth_headers)
        assert response.status_code == 422  # Validation error
        
        # Test invalid pagination
        response = client.get("/documents/?page=0", headers=auth_headers)
        assert response.status_code == 422  # Validation error
        
        response = client.get("/documents/?per_page=0", headers=auth_headers)
        assert response.status_code == 422  # Validation error
        
        response = client.get("/documents/?per_page=101", headers=auth_headers)
        assert response.status_code == 422  # Validation error