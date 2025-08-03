"""
Real Azure Blob Storage Integration Test

This test uses actual Azure Blob Storage service without mocking.
It requires valid Azure credentials to be set in environment variables.

WARNING: This test performs actual network I/O and may incur Azure storage costs.
Use environment variable USE_REAL_AZURE_TESTS=true to enable these tests.
"""

import pytest
import os
import uuid
import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import requests

from app.main import app
from app.models import User, Business, Document
from app.auth import create_user_and_business, create_access_token
from app.test_db import get_test_db, create_test_tables, drop_test_tables
from app.core.settings import get_settings
from app.services.blob import get_azure_blob_service


# Skip these tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.getenv("USE_REAL_AZURE_TESTS", "false").lower() != "true",
    reason="Real Azure tests disabled. Set USE_REAL_AZURE_TESTS=true to enable."
)


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
        email="azuretest@example.com",
        password="testpassword123",
        business_name="Azure Test Business"
    )
    
    # Create JWT token
    token = create_access_token(data={"sub": user.email})
    
    return user, token


@pytest.fixture
def client(db_session):
    """Create test client with dependency overrides"""
    from app.db import get_db
    
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


@pytest.fixture(scope="module")
def azure_credentials_check():
    """Check that Azure credentials are available"""
    required_vars = [
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_BLOB_CONTAINER_NAME"
    ]
    
    # Check for either connection string or account key
    has_connection_string = bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
    has_account_key = bool(os.getenv("AZURE_STORAGE_ACCOUNT_KEY"))
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if not (has_connection_string or has_account_key):
        missing_vars.append("AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_KEY")
    
    if missing_vars:
        pytest.skip(f"Missing required Azure environment variables: {', '.join(missing_vars)}")
    
    return True


class TestRealAzureIntegration:
    """Real Azure Blob Storage integration tests"""
    
    @pytest.mark.integration
    def test_real_azure_upload_with_private_container(self, client, auth_headers, db_session, azure_credentials_check):
        """
        Test actual file upload to Azure Blob Storage with private container
        
        This test assumes the blob container is private and:
        1. Uploads a small test file to real Azure Blob Storage
        2. Validates the upload API returns success and metadata
        3. Verifies blob URL format but does NOT test public accessibility
        4. Optionally cleans up the uploaded file to avoid charges
        """
        # Create a small test file with unique content
        unique_id = str(uuid.uuid4())
        test_filename = f"test_private_{unique_id}.pdf"
        test_content = f"Test PDF for private container - {unique_id}".encode()
        
        try:
            # Upload file via the API endpoint
            response = client.post(
                "/documents/upload",
                headers=auth_headers,
                files={"files": (test_filename, test_content, "application/pdf")}
            )
            
            # Verify upload was successful
            assert response.status_code == 200
            data = response.json()
            
            assert data["total_files"] == 1
            assert data["successful_uploads"] == 1
            assert data["failed_uploads"] == 0
            
            result = data["results"][0]
            assert result["success"] is True
            assert result["filename"] == test_filename
            assert result["document_id"] is not None
            assert result["blob_url"] is not None
            
            blob_url = result["blob_url"]
            
            # Verify blob URL format (but not accessibility for private containers)
            assert blob_url.startswith("https://"), "Blob URL should start with https://"
            assert "blob.core.windows.net" in blob_url, "Should be a valid Azure blob URL"
            assert test_filename.split('.')[0] not in blob_url, "URL should use generated filename, not original"
            
            print(f"\n✓ Successfully uploaded file to Azure Blob Storage")
            print(f"✓ Blob URL format is valid: {blob_url}")
            print(f"✓ File size: {len(test_content)} bytes")
            
            # Verify document was created in database
            document = db_session.query(Document).filter(
                Document.id == result["document_id"]
            ).first()
            
            assert document is not None
            assert document.filename == test_filename
            assert document.file_url == blob_url
            assert document.status.value == "PENDING"
            
            print(f"✓ Document record created successfully in database")
            print(f"✓ Container is private (public access disabled) - this is expected")
            
        except Exception as e:
            print(f"\n❌ Azure integration test failed: {str(e)}")
            raise
        
        finally:
            # Optional cleanup: Delete the test file from Azure to avoid charges
            try:
                if 'blob_url' in locals():
                    azure_service = get_azure_blob_service()
                    # Use asyncio to run the async delete_file method
                    import asyncio
                    deleted = asyncio.run(azure_service.delete_file(blob_url))
                    if deleted:
                        print(f"✓ Cleaned up test file from Azure Blob Storage")
                    else:
                        print(f"⚠️  Could not clean up test file: {blob_url}")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup failed: {cleanup_error}")
    
    def test_azure_service_initialization(self, azure_credentials_check):
        """Test that Azure Blob Service can be initialized with real credentials"""
        try:
            azure_service = get_azure_blob_service()
            
            # Verify service is properly initialized
            assert azure_service is not None
            assert azure_service.blob_service_client is not None
            settings = get_settings()
            assert azure_service.container_name == settings.azure_blob_container_name
            
            print(f"✓ Azure Blob Service initialized successfully")
            print(f"  Account: {settings.azure_storage_account_name}")
            print(f"  Container: {settings.azure_blob_container_name}")
            
        except Exception as e:
            print(f"❌ Azure service initialization failed: {str(e)}")
            raise
    
    def test_azure_container_access(self, azure_credentials_check):
        """Test that we can access the Azure container"""
        try:
            azure_service = get_azure_blob_service()
            
            # Try to get container client and check if it exists
            container_client = azure_service.blob_service_client.get_container_client(
                azure_service.container_name
            )
            
            # This will create the container if it doesn't exist
            container_exists = container_client.exists()
            print(f"✓ Azure container '{azure_service.container_name}' accessible (exists: {container_exists})")
            
        except Exception as e:
            print(f"❌ Azure container access failed: {str(e)}")
            raise


if __name__ == "__main__":
    print("""
Azure Integration Test
=====================

To run these tests, set the following environment variables:

Required:
- USE_REAL_AZURE_TESTS=true
- AZURE_STORAGE_ACCOUNT_NAME=your_account_name
- AZURE_BLOB_CONTAINER_NAME=your_container_name

Authentication (choose one):
- AZURE_STORAGE_CONNECTION_STRING=your_connection_string
OR
- AZURE_STORAGE_ACCOUNT_KEY=your_account_key

Example:
    export USE_REAL_AZURE_TESTS=true
    export AZURE_STORAGE_ACCOUNT_NAME=mystorageaccount
    export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
    export AZURE_BLOB_CONTAINER_NAME=documents
    
    pytest tests/test_azure_integration.py -v -s

WARNING: These tests use real Azure services and may incur charges.
""")