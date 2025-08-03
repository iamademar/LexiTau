import os
import uuid
from typing import Optional
from fastapi import UploadFile, HTTPException
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import AzureError
import logging

from ..core.settings import get_settings
from ..enums import FileType

logger = logging.getLogger(__name__)


class AzureBlobService:
    """Service for handling Azure Blob Storage operations"""
    
    def __init__(self):
        """Initialize Azure Blob Service with connection string from settings"""
        try:
            settings = get_settings()
            logger.info(f"Initializing Azure Blob Service with account: {settings.azure_storage_account_name}")
            self.blob_service_client = BlobServiceClient.from_connection_string(
                settings.azure_connection_string
            )
            self.container_name = settings.azure_blob_container_name
            self._ensure_container_exists()
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Service: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Failed to initialize blob storage service"
            )
    
    def _ensure_container_exists(self) -> None:
        """Ensure the container exists, create if it doesn't"""
        try:
            container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
            if not container_client.exists():
                # Try to create container without public access first
                try:
                    container_client.create_container()
                    logger.info(f"Created private container: {self.container_name}")
                except AzureError as create_error:
                    # If that fails, try with public access (for older storage accounts)
                    if "PublicAccessNotPermitted" in str(create_error):
                        container_client.create_container(public_access=None)
                        logger.info(f"Created private container: {self.container_name}")
                    else:
                        raise create_error
        except AzureError as e:
            logger.error(f"Failed to ensure container exists: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to access blob storage container"
            )
    
    def validate_file_type(self, file: UploadFile) -> bool:
        """
        Validate that the uploaded file is PDF, JPG, or PNG
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            bool: True if file type is valid, False otherwise
        """
        if not file.filename:
            return False
        
        # Get file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        # Check against valid extensions
        valid_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
        if file_extension not in valid_extensions:
            return False
        
        # Also check MIME type if available
        if file.content_type:
            valid_mime_types = {
                "application/pdf",
                "image/jpeg", 
                "image/jpg",
                "image/png"
            }
            if file.content_type.lower() not in valid_mime_types:
                return False
        
        return True
    
    def _get_file_type_from_filename(self, filename: str) -> FileType:
        """
        Determine FileType enum from filename extension
        
        Args:
            filename: Name of the file
            
        Returns:
            FileType: Corresponding enum value
        """
        extension = os.path.splitext(filename)[1].lower()
        
        if extension == ".pdf":
            return FileType.PDF
        elif extension in [".jpg", ".jpeg"]:
            return FileType.JPG
        elif extension == ".png":
            return FileType.PNG
        else:
            raise ValueError(f"Unsupported file extension: {extension}")
    
    def _generate_blob_name(self, user_id: uuid.UUID, filename: str) -> str:
        """
        Generate a unique blob name with user-specific path
        
        Args:
            user_id: UUID of the user uploading the file
            filename: Original filename
            
        Returns:
            str: Unique blob name with path
        """
        # Generate unique ID for the file
        file_id = uuid.uuid4()
        
        # Get file extension
        _, extension = os.path.splitext(filename)
        
        # Create user-specific path structure
        blob_name = f"users/{user_id}/documents/{file_id}{extension}"
        
        return blob_name
    
    async def upload_file(self, file: UploadFile, user_id: uuid.UUID) -> str:
        """
        Upload file to Azure Blob Storage in user-specific container path
        
        Args:
            file: FastAPI UploadFile object
            user_id: UUID of the user uploading the file
            
        Returns:
            str: URL of the uploaded blob
            
        Raises:
            HTTPException: If upload fails or file validation fails
        """
        # Validate file type
        if not self.validate_file_type(file):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF, JPG, and PNG files are allowed."
            )
        
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )
        
        try:
            # Generate unique blob name
            blob_name = self._generate_blob_name(user_id, file.filename)
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Read file content
            file_content = await file.read()
            
            # Reset file position for potential future reads
            await file.seek(0)
            
            # Determine content type
            content_type = file.content_type or self._get_content_type_from_filename(file.filename)
            
            # Upload the blob
            blob_client.upload_blob(
                data=file_content,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
            
            # Return the blob URL
            blob_url = blob_client.url
            
            logger.info(f"Successfully uploaded file {file.filename} for user {user_id} to {blob_url}")
            
            return blob_url
            
        except AzureError as e:
            logger.error(f"Azure error during file upload: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to upload file to cloud storage"
            )
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {e}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred during file upload"
            )
    
    def _get_content_type_from_filename(self, filename: str) -> str:
        """
        Get MIME content type from filename extension
        
        Args:
            filename: Name of the file
            
        Returns:
            str: MIME content type
        """
        extension = os.path.splitext(filename)[1].lower()
        
        content_types = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png"
        }
        
        return content_types.get(extension, "application/octet-stream")
    
    async def delete_file(self, blob_url: str) -> bool:
        """
        Delete a file from Azure Blob Storage
        
        Args:
            blob_url: URL of the blob to delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            # Extract blob name from URL
            blob_name = blob_url.split(f"{self.container_name}/")[1]
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Delete the blob
            blob_client.delete_blob()
            
            logger.info(f"Successfully deleted blob: {blob_name}")
            return True
            
        except AzureError as e:
            logger.error(f"Azure error during file deletion: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during file deletion: {e}")
            return False
    
    def get_file_url(self, blob_name: str) -> str:
        """
        Get the URL for a specific blob
        
        Args:
            blob_name: Name of the blob
            
        Returns:
            str: URL of the blob
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        return blob_client.url


# Global instance - will be initialized when first accessed
azure_blob_service = None

def get_azure_blob_service() -> AzureBlobService:
    """Get or create the Azure Blob Service instance"""
    global azure_blob_service
    if azure_blob_service is None:
        azure_blob_service = AzureBlobService()
    return azure_blob_service