from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import math

from ..db import get_db
from ..auth import get_current_user
from ..models import User, Document, ExtractedField, LineItem, FieldCorrection
from ..schemas.document import (
    DocumentUploadResponse, 
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
    MarkReviewedRequest,
    MarkReviewedResponse
)
from ..services.blob import get_azure_blob_service
from ..enums import FileType, DocumentType, DocumentStatus, DocumentClassification
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
        classification = determine_document_classification(document_type)
        
        # Create document record in database with PENDING status
        document = Document(
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
    is_reviewed: Optional[bool] = Query(None, description="Filter by review status (True=reviewed, False=not reviewed)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all documents for the current business with filters and pagination
    
    Supports filtering by:
    - status: PENDING, PROCESSING, COMPLETED, FAILED
    - document_type: INVOICE, RECEIPT
    - is_reviewed: True (reviewed), False (not reviewed)
    
    Returns paginated results with metadata.
    """
    # Base query for business documents
    query = db.query(Document).filter(Document.business_id == current_user.business_id)
    
    # Apply filters
    if status:
        query = query.filter(Document.status == status)
    
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    if is_reviewed is not None:
        if is_reviewed:
            query = query.filter(Document.reviewed_at.is_not(None))
        else:
            query = query.filter(Document.reviewed_at.is_(None))
    
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
            reviewed_at=doc.reviewed_at,
            reviewed_by=doc.reviewed_by,
            is_reviewed=doc.reviewed_at is not None,
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


def calculate_fields_summary(fields: List[ExtractedField]) -> Dict[str, Any]:
    """Calculate summary statistics for extracted fields"""
    if not fields:
        return {
            "total_fields": 0,
            "fields_with_values": 0,
            "fields_without_values": 0,
            "average_confidence": 0.0,
            "high_confidence_fields": 0,
            "medium_confidence_fields": 0,
            "low_confidence_fields": 0
        }
    
    total_fields = len(fields)
    fields_with_values = len([f for f in fields if f.value is not None and f.value.strip() != ""])
    
    confidences = [f.confidence for f in fields if f.confidence is not None and f.value is not None and f.value.strip() != ""]
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    high_confidence = len([c for c in confidences if c >= 0.8])
    medium_confidence = len([c for c in confidences if 0.5 <= c < 0.8])
    low_confidence = len([c for c in confidences if c < 0.5])
    
    # Count fields that are flagged as low confidence (< 0.7 or None)
    flagged_low_confidence = len([f for f in fields if is_low_confidence(f.confidence)])
    
    return {
        "total_fields": total_fields,
        "fields_with_values": fields_with_values,
        "fields_without_values": total_fields - fields_with_values,
        "average_confidence": round(average_confidence, 3),
        "high_confidence_fields": high_confidence,
        "medium_confidence_fields": medium_confidence,
        "low_confidence_fields": low_confidence,
        "flagged_low_confidence_fields": flagged_low_confidence
    }


def is_low_confidence(confidence: Optional[float]) -> bool:
    """
    Determine if a confidence score indicates low confidence.
    
    Args:
        confidence: Confidence score (0.0 to 1.0) or None
        
    Returns:
        True if confidence < 0.7 or confidence is None
    """
    if confidence is None:
        return True
    return confidence < 0.7


def build_field_responses_with_corrections(
    extracted_fields: List[ExtractedField], 
    document_id: UUID, 
    db: Session
) -> List[ExtractedFieldResponse]:
    """
    Build field responses with corrections overlay.
    
    Args:
        extracted_fields: List of ExtractedField objects
        document_id: Document UUID
        db: Database session
        
    Returns:
        List of ExtractedFieldResponse with corrected values applied
    """
    # Get the latest corrections for each field (if any)
    latest_corrections = {}
    corrections = db.query(FieldCorrection).filter(
        FieldCorrection.document_id == document_id
    ).order_by(FieldCorrection.field_name, FieldCorrection.timestamp.desc()).all()
    
    # Build a map of latest correction per field
    for correction in corrections:
        if correction.field_name not in latest_corrections:
            latest_corrections[correction.field_name] = correction
    
    # Convert to response format with corrected values overlay
    field_responses = []
    for field in extracted_fields:
        correction = latest_corrections.get(field.field_name)
        has_correction = correction is not None
        
        # If there's a correction, use corrected_value; otherwise use original value
        display_value = correction.corrected_value if has_correction else field.value
        
        field_responses.append(ExtractedFieldResponse(
            id=field.id,
            field_name=field.field_name,
            value=display_value,  # This shows corrected value if available, otherwise original
            original_value=field.value,  # Always show the original OCR value
            corrected_value=correction.corrected_value if has_correction else None,
            confidence=field.confidence,
            is_low_confidence=is_low_confidence(field.confidence),
            is_corrected=has_correction,
            created_at=field.created_at,
            updated_at=field.updated_at
        ))
    
    # Handle fields that exist only as corrections (user-added fields)
    for field_name, correction in latest_corrections.items():
        # Check if this correction is for a field that doesn't exist in ExtractedField
        existing_field = any(f.field_name == field_name for f in extracted_fields)
        if not existing_field:
            # This is a user-added field that didn't exist in OCR extraction
            field_responses.append(ExtractedFieldResponse(
                id=0,  # No original field ID
                field_name=field_name,
                value=correction.corrected_value,
                original_value=None,  # No original value since this was user-added
                corrected_value=correction.corrected_value,
                confidence=None,  # User-added fields have no confidence
                is_low_confidence=False,
                is_corrected=True,
                created_at=correction.timestamp,
                updated_at=correction.timestamp
            ))
    
    # Sort field responses by field_name for consistent ordering
    field_responses.sort(key=lambda x: x.field_name)
    return field_responses


def calculate_line_items_summary(line_items: List[LineItem]) -> Dict[str, Any]:
    """Calculate summary statistics for line items"""
    if not line_items:
        return {
            "total_line_items": 0,
            "items_with_descriptions": 0,
            "items_with_totals": 0,
            "average_confidence": 0.0,
            "total_amount": 0.0
        }
    
    total_line_items = len(line_items)
    items_with_descriptions = len([item for item in line_items if item.description is not None and item.description.strip() != ""])
    items_with_totals = len([item for item in line_items if item.total is not None])
    
    confidences = [item.confidence for item in line_items if item.confidence is not None]
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    total_amount = sum([float(item.total) for item in line_items if item.total is not None])
    
    # Count line items that are flagged as low confidence (< 0.7 or None)
    flagged_low_confidence = len([item for item in line_items if is_low_confidence(item.confidence)])
    
    return {
        "total_line_items": total_line_items,
        "items_with_descriptions": items_with_descriptions,
        "items_with_totals": items_with_totals,
        "average_confidence": round(average_confidence, 3),
        "total_amount": round(total_amount, 2),
        "flagged_low_confidence_items": flagged_low_confidence
    }


@router.get("/{document_id}/fields", response_model=DocumentFieldsResponse)
async def get_document_fields(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all extracted fields and line items for a specific document.
    
    Returns:
    - Document information (status, type, confidence)
    - All extracted fields with confidence scores
    - All line items with details
    - Summary statistics for fields and line items
    
    Works for both completed and pending document states:
    - PENDING/PROCESSING: Returns empty fields/line items with status info
    - COMPLETED: Returns full extraction results
    - FAILED: Returns error status with empty results
    """
    # Get the document and verify ownership
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.business_id == current_user.business_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied"
        )
    
    # Get extracted fields for this document
    extracted_fields = db.query(ExtractedField).filter(
        ExtractedField.document_id == document_id
    ).order_by(ExtractedField.field_name).all()
    
    # Get line items for this document
    line_items = db.query(LineItem).filter(
        LineItem.document_id == document_id
    ).order_by(LineItem.id).all()
    
    # Build field responses with corrections overlay
    field_responses = build_field_responses_with_corrections(extracted_fields, document_id, db)
    
    line_item_responses = [
        LineItemResponse(
            id=item.id,
            description=item.description,
            quantity=float(item.quantity) if item.quantity else None,
            unit_price=float(item.unit_price) if item.unit_price else None,
            total=float(item.total) if item.total else None,
            confidence=item.confidence,
            is_low_confidence=is_low_confidence(item.confidence),
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in line_items
    ]
    
    # Create document info response
    document_info = DocumentResponse(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        document_type=document.document_type,
        status=document.status,
        user_id=document.user_id,
        business_id=document.business_id,
        file_url=document.file_url,
        confidence_score=document.confidence_score,
        reviewed_at=document.reviewed_at,
        reviewed_by=document.reviewed_by,
        is_reviewed=document.reviewed_at is not None,
        created_at=document.created_at,
        updated_at=document.updated_at
    )
    
    # Calculate summary statistics
    fields_summary = calculate_fields_summary(extracted_fields)
    line_items_summary = calculate_line_items_summary(line_items)
    
    logger.info(f"Retrieved {len(extracted_fields)} fields and {len(line_items)} line items for document {document_id}")
    
    return DocumentFieldsResponse(
        document_id=document_id,
        document_info=document_info,
        extracted_fields=field_responses,
        line_items=line_item_responses,
        processing_status=document.status,
        overall_confidence=document.confidence_score,
        fields_summary=fields_summary,
        line_items_summary=line_items_summary
    )


@router.post("/{document_id}/fields/correct", response_model=FieldCorrectionsResponse)
async def correct_document_fields(
    document_id: UUID,
    corrections_request: FieldCorrectionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit corrections for extracted document fields.
    
    This endpoint allows users to correct field values that were incorrectly 
    extracted during OCR processing. Each correction is logged for audit 
    purposes and the extracted field is updated with the corrected value.
    
    Requirements:
    - User must have access to the document (same business)
    - Document must be in COMPLETED status
    - At least one correction must be provided
    
    For each correction:
    1. Log the correction in FieldCorrection table
    2. Update or create the field in ExtractedField table
    3. Track success/failure for each correction
    
    Returns updated field list and correction results.
    """
    # Validate user has access to document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.business_id == current_user.business_id
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
            detail=f"Cannot correct fields for document in {document.status.value} status. Document must be COMPLETED."
        )
    
    correction_results = []
    corrections_applied = 0
    corrections_failed = 0
    
    # Process each correction
    for correction_req in corrections_request.corrections:
        try:
            # Get existing field if it exists
            existing_field = db.query(ExtractedField).filter(
                ExtractedField.document_id == document_id,
                ExtractedField.field_name == correction_req.field_name
            ).first()
            
            original_value = existing_field.value if existing_field else None
            was_new_field = existing_field is None
            
            # Log the correction
            field_correction = FieldCorrection(
                document_id=document_id,
                field_name=correction_req.field_name,
                original_value=original_value,
                corrected_value=correction_req.corrected_value,
                corrected_by=current_user.id
            )
            db.add(field_correction)
            
            # Update or create the extracted field
            if existing_field:
                existing_field.value = correction_req.corrected_value
                existing_field.updated_at = func.now()
                message = f"Field '{correction_req.field_name}' updated successfully"
            else:
                # Create new field for correction
                new_field = ExtractedField(
                    document_id=document_id,
                    field_name=correction_req.field_name,
                    value=correction_req.corrected_value,
                    confidence=None  # User-corrected fields have no confidence score
                )
                db.add(new_field)
                message = f"New field '{correction_req.field_name}' created successfully"
            
            # Record successful correction
            correction_results.append(FieldCorrectionResult(
                field_name=correction_req.field_name,
                success=True,
                message=message,
                original_value=original_value,
                corrected_value=correction_req.corrected_value,
                was_new_field=was_new_field
            ))
            
            corrections_applied += 1
            
        except Exception as e:
            logger.error(f"Failed to process correction for field '{correction_req.field_name}': {str(e)}")
            
            # Record failed correction
            correction_results.append(FieldCorrectionResult(
                field_name=correction_req.field_name,
                success=False,
                message=f"Failed to correct field: {str(e)}",
                original_value=None,
                corrected_value=correction_req.corrected_value,
                was_new_field=False
            ))
            
            corrections_failed += 1
    
    # Commit all changes if any corrections were successful
    if corrections_applied > 0:
        try:
            db.commit()
            logger.info(f"Applied {corrections_applied} corrections to document {document_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit corrections for document {document_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save corrections to database"
            )
    
    # Get updated fields after corrections
    updated_fields = db.query(ExtractedField).filter(
        ExtractedField.document_id == document_id
    ).order_by(ExtractedField.field_name).all()
    
    # Build field responses with corrections overlay
    field_responses = build_field_responses_with_corrections(updated_fields, document_id, db)
    
    logger.info(f"Field corrections completed for document {document_id}: {corrections_applied} applied, {corrections_failed} failed")
    
    return FieldCorrectionsResponse(
        document_id=document_id,
        corrections_applied=corrections_applied,
        corrections_failed=corrections_failed,
        results=correction_results,
        updated_fields=field_responses
    )


@router.put("/{document_id}/line-items/{item_id}", response_model=LineItemUpdateResponse)
async def update_line_item(
    document_id: UUID,
    item_id: int,
    update_request: LineItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a line item for a specific document.
    
    This endpoint allows users to edit line item details such as description,
    quantity, unit price, and total amount. All fields are optional in the
    request - only provided fields will be updated.
    
    Requirements:
    - User must have access to the document (same business)
    - Document must be in COMPLETED status
    - Line item must exist and belong to the document
    - At least one field must be provided for update
    
    Validation:
    - Numeric fields (quantity, unit_price, total) must be non-negative
    - Empty description is allowed (will be set to None)
    
    Returns updated line item details.
    """
    # Validate user has access to document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.business_id == current_user.business_id
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
            detail=f"Cannot edit line items for document in {document.status.value} status. Document must be COMPLETED."
        )
    
    # Get the line item and verify it belongs to this document
    line_item = db.query(LineItem).filter(
        LineItem.id == item_id,
        LineItem.document_id == document_id
    ).first()
    
    if not line_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item not found or does not belong to this document"
        )
    
    # Check if at least one field is being updated
    update_data = update_request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update"
        )
    
    # Store original values for logging
    original_values = {
        "description": line_item.description,
        "quantity": line_item.quantity,
        "unit_price": line_item.unit_price,
        "total": line_item.total
    }
    
    try:
        # Update the line item with provided fields
        for field, value in update_data.items():
            if hasattr(line_item, field):
                setattr(line_item, field, value)
        
        # Update the timestamp
        line_item.updated_at = func.now()
        
        # Commit the changes
        db.commit()
        db.refresh(line_item)
        
        # Log the update for audit purposes
        updated_fields = list(update_data.keys())
        logger.info(f"Line item {item_id} updated for document {document_id} by user {current_user.id}. "
                   f"Updated fields: {updated_fields}. "
                   f"Original values: {original_values}")
        
        # Create response with updated line item
        line_item_response = LineItemResponse(
            id=line_item.id,
            description=line_item.description,
            quantity=float(line_item.quantity) if line_item.quantity else None,
            unit_price=float(line_item.unit_price) if line_item.unit_price else None,
            total=float(line_item.total) if line_item.total else None,
            confidence=line_item.confidence,
            is_low_confidence=is_low_confidence(line_item.confidence),
            created_at=line_item.created_at,
            updated_at=line_item.updated_at
        )
        
        logger.info(f"Successfully updated line item {item_id} for document {document_id}")
        
        return LineItemUpdateResponse(
            success=True,
            message=f"Line item updated successfully. Updated fields: {', '.join(updated_fields)}",
            line_item=line_item_response,
            document_id=document_id
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update line item {item_id} for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update line item"
        )


@router.post("/{document_id}/mark-reviewed", response_model=MarkReviewedResponse)
async def mark_document_reviewed(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a document as reviewed by the current user.
    
    This endpoint allows users to mark a document as reviewed after field validation.
    It sets the reviewed_at timestamp and records which user performed the review.
    
    Requirements:
    - User must have access to the document (same business)
    - Document must be in COMPLETED status for review
    - Can be marked as reviewed multiple times (updates timestamp and reviewer)
    
    Note: Marking as reviewed does not prevent future edits to the document.
    It's primarily used for tracking which documents have been validated by users.
    
    Returns the review timestamp and reviewer information.
    """
    # Validate user has access to document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.business_id == current_user.business_id
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
        document.reviewed_by = current_user.id
        document.updated_at = review_timestamp
        
        # Commit the changes
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document {document_id} marked as reviewed by user {current_user.id}")
        
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