from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import logging
import math

from ..db import get_db
from ..auth import get_current_user
from ..models import User, Document
from ..schemas.document import DocumentUploadResponse, DocumentUploadResult, DocumentListResponse, DocumentResponse, PaginationMeta
from ..services.blob import get_azure_blob_service
from ..enums import FileType, DocumentType, DocumentStatus
from ..tasks.ocr import dispatch_ocr_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# File size limit: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes


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


def get_file_size(file: UploadFile) -> int:
    """Get file size in bytes"""
    if not hasattr(file.file, 'seek') or not hasattr(file.file, 'tell'):
        return 0
    
    current_pos = file.file.tell()
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(current_pos)
    
    return file_size


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


async def process_single_file(
    file: UploadFile, 
    user: User, 
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
        file_size = get_file_size(file)
        if not validate_file_size(file):
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
        file_type = get_file_type_from_filename(file.filename)
        document_type = determine_document_type(file.filename)
        
        # Create document record in database with PENDING status
        document = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename=file.filename,
            file_url=blob_url,
            file_type=file_type,
            document_type=document_type,
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
            file_size=get_file_size(file) if file else 0
        )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload multiple documents with the following validations:
    - File size must be ≤ 10MB
    - File type must be PDF, JPG, or PNG
    - Files are uploaded to Azure Blob Storage
    - Document records are created with PENDING status
    - OCR processing tasks are dispatched (TODO)
    
    Returns upload status for each file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    if len(files) > 10:  # Limit to 10 files per request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many files. Maximum 10 files per request."
        )
    
    # Process each file
    results = []
    for file in files:
        result = await process_single_file(file, current_user, db)
        results.append(result)
    
    # Calculate summary statistics
    successful_uploads = sum(1 for r in results if r.success)
    failed_uploads = len(results) - successful_uploads
    
    return DocumentUploadResponse(
        total_files=len(files),
        successful_uploads=successful_uploads,
        failed_uploads=failed_uploads,
        results=results
    )


@router.get("/", response_model=DocumentListResponse)
async def list_business_documents(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by document status"),
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all documents for the current business with filters and pagination
    
    Supports filtering by:
    - status: PENDING, PROCESSING, COMPLETED, FAILED
    - document_type: INVOICE, RECEIPT
    
    Returns paginated results with metadata.
    """
    # Base query for business documents
    query = db.query(Document).filter(Document.business_id == current_user.business_id)
    
    # Apply filters
    if status:
        query = query.filter(Document.status == status)
    
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    # Count total items for pagination
    total_items = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0
    offset = (page - 1) * per_page
    
    # Apply pagination and ordering (newest first)
    documents = query.order_by(Document.created_at.desc()).offset(offset).limit(per_page).all()
    
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
            created_at=doc.created_at,
            updated_at=doc.updated_at
        )
        for doc in documents
    ]
    
    logger.info(f"Retrieved {len(documents)} documents for business {current_user.business_id} (page {page}/{total_pages})")
    
    return DocumentListResponse(
        documents=document_responses,
        pagination=pagination
    )