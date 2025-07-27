from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import logging

from ..db import get_db
from ..auth import get_current_user
from ..models import User, Document
from ..schemas.document import DocumentUploadResponse, DocumentUploadResult
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
        
        # Create document record in database
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
        
        # Dispatch OCR processing task (placeholder for B4)
        dispatch_ocr_task(document.id)
        
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


@router.get("/", response_model=List[DocumentUploadResult])
async def list_user_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documents for the current user"""
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    
    return [
        DocumentUploadResult(
            success=True,
            filename=doc.filename,
            document_id=doc.id,
            blob_url=doc.file_url,
            file_type=doc.file_type
        )
        for doc in documents
    ]