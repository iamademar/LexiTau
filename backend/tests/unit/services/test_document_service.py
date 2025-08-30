import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from uuid import UUID, uuid4
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.document_service import (
    FileValidationService,
    DocumentClassificationService,
    DocumentProcessingService,
    DocumentQueryService,
    DocumentManagementService
)
from app.enums import FileType, DocumentType, DocumentClassification, DocumentStatus
from app.models import User, Document


class TestFileValidationService:
    """Test cases for FileValidationService."""
    
    def test_validate_file_size_valid_file(self):
        """Test file size validation passes for valid file."""
        # Arrange
        mock_file = Mock(spec=UploadFile)
        mock_file.file = Mock()
        mock_file.file.seek = Mock()
        mock_file.file.tell = Mock(side_effect=[0, 1024])  # current pos, file size
        
        # Act
        result = FileValidationService.validate_file_size(mock_file)
        
        # Assert
        assert result is True
    
    def test_validate_file_size_invalid_file(self):
        """Test file size validation fails for oversized file."""
        # Arrange
        mock_file = Mock(spec=UploadFile)
        mock_file.file = Mock()
        mock_file.file.seek = Mock()
        mock_file.file.tell = Mock(side_effect=[0, 20*1024*1024])  # 20MB file
        
        # Act
        result = FileValidationService.validate_file_size(mock_file)
        
        # Assert
        assert result is False
    
    def test_get_file_type_from_filename_pdf(self):
        """Test getting file type for PDF files."""
        result = FileValidationService.get_file_type_from_filename("document.pdf")
        assert result == FileType.PDF
    
    def test_get_file_type_from_filename_jpg(self):
        """Test getting file type for JPG files."""
        result = FileValidationService.get_file_type_from_filename("image.jpg")
        assert result == FileType.JPG
        
        result = FileValidationService.get_file_type_from_filename("image.jpeg")
        assert result == FileType.JPG
    
    def test_get_file_type_from_filename_png(self):
        """Test getting file type for PNG files."""
        result = FileValidationService.get_file_type_from_filename("image.png")
        assert result == FileType.PNG
    
    def test_get_file_type_from_filename_unsupported(self):
        """Test getting file type for unsupported files raises error."""
        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidationService.get_file_type_from_filename("document.txt")


class TestDocumentClassificationService:
    """Test cases for DocumentClassificationService."""
    
    def test_determine_document_type_invoice(self):
        """Test document type determination for invoices."""
        result = DocumentClassificationService.determine_document_type("invoice_001.pdf")
        assert result == DocumentType.INVOICE
        
        result = DocumentClassificationService.determine_document_type("bill_002.pdf")
        assert result == DocumentType.INVOICE
        
        result = DocumentClassificationService.determine_document_type("inv_003.pdf")
        assert result == DocumentType.INVOICE
    
    def test_determine_document_type_receipt(self):
        """Test document type determination for receipts."""
        result = DocumentClassificationService.determine_document_type("receipt_001.pdf")
        assert result == DocumentType.RECEIPT
        
        result = DocumentClassificationService.determine_document_type("rec_002.pdf")
        assert result == DocumentType.RECEIPT
    
    def test_determine_document_type_default(self):
        """Test document type determination defaults to invoice."""
        result = DocumentClassificationService.determine_document_type("document.pdf")
        assert result == DocumentType.INVOICE
    
    def test_determine_document_classification_invoice(self):
        """Test document classification for invoices."""
        result = DocumentClassificationService.determine_document_classification(DocumentType.INVOICE)
        assert result == DocumentClassification.REVENUE
    
    def test_determine_document_classification_receipt(self):
        """Test document classification for receipts."""
        result = DocumentClassificationService.determine_document_classification(DocumentType.RECEIPT)
        assert result == DocumentClassification.EXPENSE
    
    def test_determine_document_classification_default(self):
        """Test document classification defaults to expense."""
        # Test with a hypothetical new document type
        result = DocumentClassificationService.determine_document_classification(None)
        assert result == DocumentClassification.EXPENSE


class TestDocumentProcessingService:
    """Test cases for DocumentProcessingService."""
    
    @pytest.mark.asyncio
    async def test_process_single_file_success(self):
        """Test successful file processing."""
        # Arrange
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_invoice.pdf"
        
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.business_id = 1
        
        mock_db = Mock(spec=Session)
        mock_document = Mock(spec=Document)
        mock_document.id = uuid4()
        
        with patch.object(FileValidationService, 'get_file_size', return_value=1024), \
             patch.object(FileValidationService, 'validate_file_size', return_value=True), \
             patch('app.services.document_service.get_azure_blob_service') as mock_blob_service, \
             patch.object(FileValidationService, 'get_file_type_from_filename', return_value=FileType.PDF), \
             patch.object(DocumentClassificationService, 'determine_document_type', return_value=DocumentType.INVOICE), \
             patch.object(DocumentClassificationService, 'determine_document_classification', return_value=DocumentClassification.REVENUE), \
             patch('app.services.document_service.dispatch_ocr_task', return_value="task_123"):
            
            mock_blob_service.return_value.validate_file_type.return_value = True
            mock_blob_service.return_value.upload_file = AsyncMock(return_value="https://blob.url/file")
            
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            # Act
            result = await DocumentProcessingService.process_single_file(mock_file, mock_user, mock_db)
            
            # Assert
            assert result.success is True
            assert result.filename == "test_invoice.pdf"
            assert result.file_size == 1024
            assert result.file_type == FileType.PDF
    
    @pytest.mark.asyncio
    async def test_process_single_file_no_filename(self):
        """Test file processing fails when no filename."""
        # Arrange
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = None
        
        mock_user = Mock(spec=User)
        mock_db = Mock(spec=Session)
        
        # Act
        result = await DocumentProcessingService.process_single_file(mock_file, mock_user, mock_db)
        
        # Assert
        assert result.success is False
        assert "Filename is required" in result.error_message
    
    @pytest.mark.asyncio
    async def test_process_single_file_oversized(self):
        """Test file processing fails for oversized file."""
        # Arrange
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "large_file.pdf"
        
        mock_user = Mock(spec=User)
        mock_db = Mock(spec=Session)
        
        with patch.object(FileValidationService, 'get_file_size', return_value=20*1024*1024), \
             patch.object(FileValidationService, 'validate_file_size', return_value=False):
            
            # Act
            result = await DocumentProcessingService.process_single_file(mock_file, mock_user, mock_db)
            
            # Assert
            assert result.success is False
            assert "File size exceeds limit" in result.error_message


class TestDocumentQueryService:
    """Test cases for DocumentQueryService."""
    
    def test_list_business_documents_basic(self):
        """Test basic document listing functionality."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_filter = Mock()
        mock_order_by = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Chain the query methods
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.count.return_value = 0
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.offset.return_value = mock_offset
        mock_offset.limit.return_value = mock_limit
        mock_limit.all.return_value = []
        
        # Act
        result = DocumentQueryService.list_business_documents(mock_db, business_id=1)
        
        # Assert
        assert hasattr(result, 'documents')
        assert hasattr(result, 'pagination')
        assert result.pagination.total_items == 0


class TestDocumentManagementService:
    """Test cases for DocumentManagementService."""
    
    def test_mark_document_reviewed_success(self):
        """Test successful document review marking."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_document = Mock(spec=Document)
        document_id = uuid4()
        mock_document.id = document_id
        mock_document.status = DocumentStatus.COMPLETED
        
        # Set up datetime attributes that will be set during the operation
        review_time = datetime.now()
        mock_document.reviewed_at = review_time
        mock_document.reviewed_by = 1
        mock_document.updated_at = review_time
        
        mock_query = Mock()
        mock_filter = Mock()
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_document
        
        user_id = 1
        business_id = 1
        
        # Mock SQLAlchemy func.now() to return actual datetime
        with patch('app.services.document_service.func') as mock_func:
            mock_func.now.return_value = review_time
            
            # Act
            result = DocumentManagementService.mark_document_reviewed(
                mock_db, document_id, user_id, business_id
            )
            
            # Assert
            assert result.success is True
            assert result.document_id == document_id
            mock_db.commit.assert_called_once()
    
    def test_mark_document_reviewed_not_found(self):
        """Test document review marking fails when document not found."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_filter = Mock()
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None  # Document not found
        
        document_id = uuid4()
        user_id = 1
        business_id = 1
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            DocumentManagementService.mark_document_reviewed(
                mock_db, document_id, user_id, business_id
            )
        
        assert exc_info.value.status_code == 404
        assert "Document not found" in exc_info.value.detail
    
    def test_mark_document_reviewed_wrong_status(self):
        """Test document review marking fails for non-completed documents."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_document = Mock(spec=Document)
        mock_document.status = DocumentStatus.PENDING  # Not completed
        
        mock_query = Mock()
        mock_filter = Mock()
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_document
        
        document_id = uuid4()
        user_id = 1
        business_id = 1
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            DocumentManagementService.mark_document_reviewed(
                mock_db, document_id, user_id, business_id
            )
        
        assert exc_info.value.status_code == 400
        assert "Cannot mark document in" in exc_info.value.detail