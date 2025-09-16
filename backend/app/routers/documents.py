from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import math

from ..dependencies import get_db, get_current_user
from .. import models
from ..schemas import (
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
    MarkReviewedResponse,
    DocumentTagRequest,
    DocumentTagResponse
)
from ..enums import FileType, DocumentType, DocumentStatus, DocumentClassification
from ..services.document_service import (
    DocumentProcessingService, 
    DocumentQueryService,
    DocumentManagementService
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])



@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload multiple documents with the following validations:
    - File size must be ≤ 10MB
    - File type must be PDF, JPG, or PNG
    - Files are uploaded to Azure Blob Storage
    - models.Document records are created with PENDING status
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
        result = await DocumentProcessingService.process_single_file(file, current_user, db)
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
    classification: Optional[DocumentClassification] = Query(None, description="Filter by document classification (revenue or expense)"),
    is_reviewed: Optional[bool] = Query(None, description="Filter by review status (True=reviewed, False=not reviewed)"),
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),  
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all documents for the current business with filters and pagination
    
    Supports filtering by:
    - status: PENDING, PROCESSING, COMPLETED, FAILED
    - document_type: INVOICE, RECEIPT
    - classification: REVENUE, EXPENSE
    - is_reviewed: True (reviewed), False (not reviewed)
    - client_id: Filter by associated client
    - project_id: Filter by associated project
    - category_id: Filter by associated category
    
    Tag filters (client_id, project_id, category_id) validate ownership to ensure
    users can only filter by tags that belong to their business.
    
    Returns paginated results with metadata.
    """
    return DocumentQueryService.list_business_documents(
        db=db,
        business_id=current_user.business_id,
        page=page,
        per_page=per_page,
        status=status,
        document_type=document_type,
        classification=classification,
        is_reviewed=is_reviewed,
        client_id=client_id,
        project_id=project_id,
        category_id=category_id
    )


def calculate_fields_summary(fields: List[models.ExtractedField]) -> Dict[str, Any]:
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
    extracted_fields: List[models.ExtractedField],
    document_id: UUID,
    business_id: int,
    db: Session
) -> List[ExtractedFieldResponse]:
    """
    Build field responses with corrections overlay.
    
    Args:
        extracted_fields: List of models.ExtractedField objects
        document_id: models.Document UUID
        db: Database session
        
    Returns:
        List of ExtractedFieldResponse with corrected values applied
    """
    # Get the latest corrections for each field (if any)
    latest_corrections = {}
    corrections = db.query(models.FieldCorrection).filter(
        models.FieldCorrection.document_id == document_id,
        models.FieldCorrection.business_id == business_id
    ).order_by(models.FieldCorrection.field_name, models.FieldCorrection.timestamp.desc()).all()
    
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
        # Check if this correction is for a field that doesn't exist in models.ExtractedField
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


def calculate_line_items_summary(line_items: List[models.LineItem]) -> Dict[str, Any]:
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all extracted fields and line items for a specific document.
    
    Returns:
    - models.Document information (status, type, confidence)
    - All extracted fields with confidence scores
    - All line items with details
    - Summary statistics for fields and line items
    
    Works for both completed and pending document states:
    - PENDING/PROCESSING: Returns empty fields/line items with status info
    - COMPLETED: Returns full extraction results
    - FAILED: Returns error status with empty results
    """
    # Get the document and verify ownership
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.business_id == current_user.business_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="models.Document not found or access denied"
        )
    
    # Get extracted fields for this document
    extracted_fields = db.query(models.ExtractedField).filter(
        models.ExtractedField.document_id == document_id,
        models.ExtractedField.business_id == current_user.business_id
    ).order_by(models.ExtractedField.field_name).all()
    
    # Get line items for this document
    line_items = db.query(models.LineItem).filter(
        models.LineItem.document_id == document_id,
        models.LineItem.business_id == current_user.business_id
    ).order_by(models.LineItem.id).all()
    
    # Build field responses with corrections overlay
    field_responses = build_field_responses_with_corrections(extracted_fields, document_id, current_user.business_id, db)
    
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit corrections for extracted document fields.
    
    This endpoint allows users to correct field values that were incorrectly 
    extracted during OCR processing. Each correction is logged for audit 
    purposes and the extracted field is updated with the corrected value.
    
    Requirements:
    - User must have access to the document (same business)
    - models.Document must be in COMPLETED status
    - At least one correction must be provided
    
    For each correction:
    1. Log the correction in models.FieldCorrection table
    2. Update or create the field in models.ExtractedField table
    3. Track success/failure for each correction
    
    Returns updated field list and correction results.
    """
    # Validate user has access to document
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.business_id == current_user.business_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="models.Document not found or access denied"
        )
    
    # Validate document is in COMPLETED state
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot correct fields for document in {document.status.value} status. models.Document must be COMPLETED."
        )
    
    correction_results = []
    corrections_applied = 0
    corrections_failed = 0
    
    # Process each correction
    for correction_req in corrections_request.corrections:
        try:
            # Get existing field if it exists
            existing_field = db.query(models.ExtractedField).filter(
                models.ExtractedField.document_id == document_id,
                models.ExtractedField.business_id == current_user.business_id,
                models.ExtractedField.field_name == correction_req.field_name
            ).first()
            
            original_value = existing_field.value if existing_field else None
            was_new_field = existing_field is None
            
            # Log the correction
            field_correction = models.FieldCorrection(
                document_id=document_id,
                business_id=current_user.business_id,
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
                new_field = models.ExtractedField(
                    document_id=document_id,
                    business_id=current_user.business_id,
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
    updated_fields = db.query(models.ExtractedField).filter(
        models.ExtractedField.document_id == document_id,
        models.ExtractedField.business_id == current_user.business_id
    ).order_by(models.ExtractedField.field_name).all()

    # Build field responses with corrections overlay
    field_responses = build_field_responses_with_corrections(updated_fields, document_id, current_user.business_id, db)
    
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a line item for a specific document.
    
    This endpoint allows users to edit line item details such as description,
    quantity, unit price, and total amount. All fields are optional in the
    request - only provided fields will be updated.
    
    Requirements:
    - User must have access to the document (same business)
    - models.Document must be in COMPLETED status
    - Line item must exist and belong to the document
    - At least one field must be provided for update
    
    Validation:
    - Numeric fields (quantity, unit_price, total) must be non-negative
    - Empty description is allowed (will be set to None)
    
    Returns updated line item details.
    """
    # Validate user has access to document
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.business_id == current_user.business_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="models.Document not found or access denied"
        )
    
    # Validate document is in COMPLETED state
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit line items for document in {document.status.value} status. models.Document must be COMPLETED."
        )
    
    # Get the line item and verify it belongs to this document
    line_item = db.query(models.LineItem).filter(
        models.LineItem.id == item_id,
        models.LineItem.document_id == document_id,
        models.LineItem.business_id == current_user.business_id
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
    current_user: models.User = Depends(get_current_user),
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
    return DocumentManagementService.mark_document_reviewed(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        business_id=current_user.business_id
    )


@router.put("/{document_id}/tag", response_model=DocumentTagResponse)
async def tag_document(
    document_id: UUID,
    tag_request: DocumentTagRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Tag a document with client, project, and/or category.
    
    This endpoint allows users to associate documents with clients, projects, and categories
    for better organization and reporting. All tag fields are optional.
    
    Requirements:
    - User must have access to the document (same business)
    - Client and project must belong to the same business as the user
    - Category can be any valid category (categories are global)
    
    Business Logic:
    - Validates ownership of document, client, and project
    - Allows null values for optional fields (project_id, category_id)
    - Updates document metadata with tag associations
    - Records timestamp of tagging operation
    
    Returns updated document metadata with tag information.
    """
    # Validate user has access to document
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.business_id == current_user.business_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied"
        )
    
    # Validate client ownership if client_id is provided
    if tag_request.client_id is not None:
        client = db.query(models.Client).filter(
            models.Client.id == tag_request.client_id,
            models.Client.business_id == current_user.business_id
        ).first()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client not found or access denied. Client must belong to your business."
            )
    
    # Validate project ownership if project_id is provided  
    if tag_request.project_id is not None:
        project = db.query(models.Project).filter(
            models.Project.id == tag_request.project_id,
            models.Project.business_id == current_user.business_id
        ).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project not found or access denied. Project must belong to your business."
            )
    
    # Validate category exists if category_id is provided (categories are global)
    if tag_request.category_id is not None:
        category = db.query(models.Category).filter(
            models.Category.id == tag_request.category_id
        ).first()
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found."
            )
    
    try:
        # Update document with tag information (only update fields that are explicitly provided)
        update_data = tag_request.model_dump(exclude_unset=True)
        
        if "client_id" in update_data:
            document.client_id = tag_request.client_id
        if "project_id" in update_data:
            document.project_id = tag_request.project_id  
        if "category_id" in update_data:
            document.category_id = tag_request.category_id
            
        document.updated_at = func.now()
        
        # Commit the changes
        db.commit()
        db.refresh(document)
        
        # Log the tagging operation for audit purposes
        logger.info(f"Document {document_id} tagged by user {current_user.id}. "
                   f"Client: {tag_request.client_id}, Project: {tag_request.project_id}, "
                   f"Category: {tag_request.category_id}")
        
        return DocumentTagResponse(
            success=True,
            message="Document tagged successfully",
            document_id=document_id,
            client_id=document.client_id,
            project_id=document.project_id,
            category_id=document.category_id,
            updated_at=document.updated_at
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to tag document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to tag document"
        )