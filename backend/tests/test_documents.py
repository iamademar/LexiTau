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


class TestDocumentList:
    """Test cases for listing user documents"""
    
    def test_list_user_documents(self, client, auth_headers, test_user_and_token, db_session):
        """Test listing documents for authenticated user"""
        user, token = test_user_and_token
        
        # Create test documents
        doc1 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="doc1.pdf",
            file_url="https://example.com/doc1.pdf",
            file_type="PDF",
            document_type="INVOICE",
            status="PENDING"
        )
        doc2 = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="doc2.jpg",
            file_url="https://example.com/doc2.jpg",
            file_type="JPG",
            document_type="RECEIPT",
            status="COMPLETED"
        )
        
        db_session.add_all([doc1, doc2])
        db_session.commit()
        
        response = client.get("/documents/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        filenames = {doc["filename"] for doc in data}
        assert filenames == {"doc1.pdf", "doc2.jpg"}
    
    def test_list_documents_without_auth(self, client):
        """Test listing documents without authentication"""
        response = client.get("/documents/")
        assert response.status_code == 403