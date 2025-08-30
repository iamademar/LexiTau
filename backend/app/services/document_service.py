from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status, UploadFile
import logging
import math

from .. import models
from ..enums import FileType, DocumentType, DocumentStatus, DocumentClassification
from ..schemas import (
    DocumentUploadResult, 
    DocumentListResponse,
    DocumentResponse,
    PaginationMeta,
    DocumentFieldsResponse,
    ExtractedFieldResponse,
    LineItemResponse,
    FieldCorrectionsRequest,
    FieldCorrectionsResponse,
    FieldCorrectionResult,
    LineItemUpdateRequest,
    LineItemUpdateResponse,
    MarkReviewedResponse
)
from .blob import get_azure_blob_service
from ..tasks.ocr import dispatch_ocr_task

logger = logging.getLogger(__name__)

# File size limit: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes


class FileValidationService:
    """Service for file validation operations."""
    
    @staticmethod
    def validate_file_size(file: UploadFile) -> bool:
        """Validate file size is under the limit"""
        if not hasattr(file.file, 'seek') or not hasattr(file.file, 'tell'):
            return True  # Can't check size, allow it
        
        # Get current position
        current_pos = file.file.tell()
        
        # Seek to end to get file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        
        # Reset to original position
        file.file.seek(current_pos)
        
        return file_size <= MAX_FILE_SIZE
    
    @staticmethod
    def get_file_size(file: UploadFile) -> int:
        """Get file size in bytes"""
        if not hasattr(file.file, 'seek') or not hasattr(file.file, 'tell'):
            return 0
        
        current_pos = file.file.tell()
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(current_pos)
        
        return file_size
    
    @staticmethod
    def get_file_type_from_filename(filename: str) -> FileType:
        """Get FileType enum from filename extension"""
        import os
        extension = os.path.splitext(filename)[1].lower()
        
        if extension == ".pdf":
            return FileType.PDF
        elif extension in [".jpg", ".jpeg"]:
            return FileType.JPG
        elif extension == ".png":
            return FileType.PNG
        else:
            raise ValueError(f"Unsupported file extension: {extension}")


class DocumentClassificationService:
    """Service for document type and classification logic."""
    
    @staticmethod
    def determine_document_type(filename: str) -> DocumentType:
        """Determine document type based on filename (placeholder logic)"""
        filename_lower = filename.lower()
        
        if any(keyword in filename_lower for keyword in ['invoice', 'bill', 'inv']):
            return DocumentType.INVOICE
        elif any(keyword in filename_lower for keyword in ['receipt', 'rec']):
            return DocumentType.RECEIPT
        else:
            # Default to invoice if we can't determine
            return DocumentType.INVOICE
    
    @staticmethod
    def determine_document_classification(document_type: DocumentType) -> DocumentClassification:
        """
        Automatically classify document based on document type:
        - INVOICE → REVENUE 
        - RECEIPT → EXPENSE
        """
        if document_type == DocumentType.INVOICE:
            return DocumentClassification.REVENUE
        elif document_type == DocumentType.RECEIPT:
            return DocumentClassification.EXPENSE
        else:
            # Default to EXPENSE if unknown type
            return DocumentClassification.EXPENSE


class DocumentProcessingService:
    """Service for document processing operations."""
    
    @staticmethod
    async def process_single_file(
        file: UploadFile, 
        user: models.User, 
        db: Session
    ) -> DocumentUploadResult:
        """Process a single file upload"""
        try:
            # Basic validation
            if not file.filename:
                return DocumentUploadResult(
                    success=False,
                    filename=file.filename or "unknown",
                    error_message="Filename is required"
                )
            
            # Validate file size
            file_size = FileValidationService.get_file_size(file)
            if not FileValidationService.validate_file_size(file):
                return DocumentUploadResult(
                    success=False,
                    filename=file.filename,
                    error_message=f"File size exceeds limit of {MAX_FILE_SIZE / (1024*1024):.1f}MB",
                    file_size=file_size
                )
            
            # Validate file type
            azure_service = get_azure_blob_service()
            if not azure_service.validate_file_type(file):
                return DocumentUploadResult(
                    success=False,
                    filename=file.filename,
                    error_message="Invalid file type. Only PDF, JPG, and PNG files are allowed.",
                    file_size=file_size
                )
            
            # Upload to Azure Blob Storage
            blob_url = await azure_service.upload_file(file, user.id)
            
            # Determine file and document types
            file_type = FileValidationService.get_file_type_from_filename(file.filename)
            document_type = DocumentClassificationService.determine_document_type(file.filename)
            classification = DocumentClassificationService.determine_document_classification(document_type)
            
            # Create document record in database with PENDING status
            document = models.Document(
                user_id=user.id,
                business_id=user.business_id,
                filename=file.filename,
                file_url=blob_url,
                file_type=file_type,
                document_type=document_type,
                classification=classification,
                status=DocumentStatus.PENDING
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            # Dispatch OCR processing task and update status to PROCESSING
            task_id = dispatch_ocr_task(document.id)
            
            # Update status to PROCESSING after successful task dispatch
            document.status = DocumentStatus.PROCESSING
            db.commit()
            
            logger.info(f"Document {document.id} queued for processing with task ID: {task_id}")
            logger.info(f"Successfully uploaded document {document.id} for user {user.id}")
            
            return DocumentUploadResult(
                success=True,
                filename=file.filename,
                document_id=document.id,
                blob_url=blob_url,
                file_size=file_size,
                file_type=file_type
            )
            
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}")
            return DocumentUploadResult(
                success=False,
                filename=file.filename or "unknown",
                error_message=f"Upload failed: {str(e)}",
                file_size=FileValidationService.get_file_size(file) if file else 0
            )


class DocumentQueryService:
    """Service for document querying and listing operations."""
    
    @staticmethod
    def list_business_documents(
        db: Session,
        business_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[DocumentStatus] = None,
        document_type: Optional[DocumentType] = None,
        is_reviewed: Optional[bool] = None
    ) -> DocumentListResponse:
        """
        List all documents for a business with filters and pagination.
        
        Args:
            db: Database session
            business_id: Business ID to filter documents
            page: Page number (1-based)
            per_page: Items per page
            status: Optional status filter
            document_type: Optional document type filter  
            is_reviewed: Optional review status filter
            
        Returns:
            DocumentListResponse with paginated documents
        """
        # Base query for business documents
        query = db.query(models.Document).filter(models.Document.business_id == business_id)
        
        # Apply filters
        if status:
            query = query.filter(models.Document.status == status)
        
        if document_type:
            query = query.filter(models.Document.document_type == document_type)
        
        if is_reviewed is not None:
            if is_reviewed:
                query = query.filter(models.Document.reviewed_at.is_not(None))
            else:
                query = query.filter(models.Document.reviewed_at.is_(None))
        
        # Count total items for pagination
        total_items = query.count()
        
        # Calculate pagination
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0
        offset = (page - 1) * per_page
        
        # Apply pagination and ordering (newest first)
        documents = query.order_by(models.Document.created_at.desc()).offset(offset).limit(per_page).all()
        
        # Create pagination metadata
        pagination = PaginationMeta(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        # Convert to response format
        document_responses = [
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                document_type=doc.document_type,
                status=doc.status,
                user_id=doc.user_id,
                business_id=doc.business_id,
                file_url=doc.file_url,
                confidence_score=doc.confidence_score,
                reviewed_at=doc.reviewed_at,
                reviewed_by=doc.reviewed_by,
                is_reviewed=doc.reviewed_at is not None,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )
            for doc in documents
        ]
        
        logger.info(f"Retrieved {len(documents)} documents for business {business_id} (page {page}/{total_pages})")
        
        return DocumentListResponse(
            documents=document_responses,
            pagination=pagination
        )


class DocumentManagementService:
    """Service for document management operations like marking reviewed."""
    
    @staticmethod
    def mark_document_reviewed(
        db: Session, 
        document_id: UUID, 
        user_id: int, 
        business_id: int
    ) -> MarkReviewedResponse:
        """
        Mark a document as reviewed by the current user.
        
        Args:
            db: Database session
            document_id: Document UUID
            user_id: Current user ID
            business_id: Current user's business ID
            
        Returns:
            MarkReviewedResponse with success status
            
        Raises:
            HTTPException: If document not found or invalid status
        """
        # Validate user has access to document
        document = db.query(models.Document).filter(
            models.Document.id == document_id,
            models.Document.business_id == business_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied"
            )
        
        # Validate document is in COMPLETED state
        if document.status != DocumentStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot mark document in {document.status.value} status as reviewed. Document must be COMPLETED."
            )
        
        try:
            # Mark document as reviewed
            review_timestamp = func.now()
            document.reviewed_at = review_timestamp
            document.reviewed_by = user_id
            document.updated_at = review_timestamp
            
            # Commit the changes
            db.commit()
            db.refresh(document)
            
            logger.info(f"Document {document_id} marked as reviewed by user {user_id}")
            
            return MarkReviewedResponse(
                success=True,
                message="Document marked as reviewed successfully",
                document_id=document_id,
                reviewed_at=document.reviewed_at,
                reviewed_by=document.reviewed_by
            )
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark document {document_id} as reviewed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark document as reviewed"
            )