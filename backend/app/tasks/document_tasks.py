import uuid
import logging
import asyncio
from typing import Dict, Any, List
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.celery import celery_app
from app.db import get_db
from app.models import Document, ExtractedField, LineItem
from app.enums import DocumentStatus, DocumentType
from app.services.azure_form_recognizer import get_azure_form_recognizer_client, DocumentExtractionError

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def process_document_ocr(self, document_id: str) -> dict:
    """
    Process document OCR asynchronously using Azure Form Recognizer
    
    This task:
    1. Fetches the document from database
    2. Calls Azure Form Recognizer to extract fields
    3. Normalizes and saves extracted fields to database
    4. Updates document status and confidence score
    
    Args:
        document_id: UUID string of the document to process
        
    Returns:
        Dictionary with processing results
    """
    db = None
    try:
        logger.info(f"Starting OCR processing for document {document_id}")
        
        # Get database session
        db = next(get_db())
        
        # 1. Fetch document from database
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        logger.info(f"Processing document: {document.filename} (type: {document.document_type})")
        
        # 2. Call Azure Form Recognizer (run async in sync context)
        azure_client = get_azure_form_recognizer_client()
        
        # Run the async extraction in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            extraction_result = loop.run_until_complete(
                azure_client.extract_fields(
                    file_url=document.file_url,
                    document_type=document.document_type
                )
            )
        finally:
            loop.close()
        
        # 3. Normalize and save extracted fields
        fields_saved = _save_extracted_fields(db, document, extraction_result["fields"])
        line_items_saved = _save_line_items(db, document, extraction_result["line_items"])
        
        # 4. Calculate overall confidence score
        overall_confidence = _calculate_overall_confidence(
            extraction_result["fields"], 
            extraction_result["line_items"]
        )
        
        # 5. Update document status and confidence
        logger.info(f"Before status update - Document {document_id} current status: {document.status}")
        document.status = DocumentStatus.COMPLETED
        document.confidence_score = overall_confidence
        logger.info(f"After status update - Document {document_id} new status: {document.status}, confidence: {overall_confidence}")
        
        try:
            db.commit()
            logger.info(f"Database commit successful for document {document_id}")
            
            # Verify the update was persisted
            db.refresh(document)
            logger.info(f"After refresh - Document {document_id} status in DB: {document.status}")
        except Exception as commit_error:
            logger.error(f"Database commit failed for document {document_id}: {commit_error}")
            db.rollback()
            raise
        
        result = {
            "document_id": document_id,
            "status": "completed",
            "fields_extracted": fields_saved,
            "line_items_extracted": line_items_saved,
            "overall_confidence": overall_confidence,
            "document_type": document.document_type.value
        }
        
        logger.info(f"OCR processing completed for document {document_id}: "
                   f"{fields_saved} fields, {line_items_saved} line items, "
                   f"confidence: {overall_confidence:.2f}")
        
        return result
        
    except DocumentExtractionError as exc:
        logger.error(f"Azure extraction failed for document {document_id}: {exc}")
        _update_document_status_failed(db, document_id, str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)
        
    except Exception as exc:
        logger.error(f"OCR processing failed for document {document_id}: {exc}")
        _update_document_status_failed(db, document_id, str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)
        
    finally:
        if db:
            db.close()


@celery_app.task(bind=True)
def process_document_classification(self, document_id: str) -> dict:
    """
    Classify document type (invoice, receipt, etc.)
    
    Args:
        document_id: UUID string of the document to classify
        
    Returns:
        Dictionary with classification results
    """
    try:
        logger.info(f"Starting classification for document {document_id}")
        
        # TODO: Implement actual document classification
        # This is a placeholder implementation
        
        result = {
            "document_id": document_id,
            "document_type": "invoice",
            "confidence": 0.92,
            "categories": ["financial", "invoice"]
        }
        
        logger.info(f"Classification completed for document {document_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Classification failed for document {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)


def dispatch_ocr_task(document_id: uuid.UUID) -> str:
    """
    Dispatch OCR task to Celery worker
    
    This replaces the placeholder function in ocr.py
    
    Args:
        document_id: UUID of the document to process
        
    Returns:
        Task ID for tracking
    """
    task = process_document_ocr.delay(str(document_id))
    logger.info(f"Dispatched OCR task {task.id} for document {document_id}")
    return task.id


def dispatch_classification_task(document_id: uuid.UUID) -> str:
    """
    Dispatch classification task to Celery worker
    
    Args:
        document_id: UUID of the document to classify
        
    Returns:
        Task ID for tracking
    """
    task = process_document_classification.delay(str(document_id))
    logger.info(f"Dispatched classification task {task.id} for document {document_id}")
    return task.id


# Helper functions for OCR processing

def _save_extracted_fields(db: Session, document: Document, fields: List[Dict[str, Any]]) -> int:
    """
    Save extracted fields to database
    
    Args:
        db: Database session
        document: Document instance
        fields: List of extracted fields from Azure
        
    Returns:
        Number of fields saved
    """
    fields_saved = 0
    
    for field_data in fields:
        try:
            # Create ExtractedField instance
            extracted_field = ExtractedField(
                document_id=document.id,
                field_name=field_data["field_name"],
                value=field_data["value"],
                confidence=field_data["confidence"]
            )
            
            db.add(extracted_field)
            fields_saved += 1
            
            logger.debug(f"Saved field {field_data['field_name']}: "
                        f"{field_data['value']} (confidence: {field_data['confidence']:.2f})")
            
        except Exception as e:
            logger.warning(f"Failed to save field {field_data.get('field_name', 'unknown')}: {e}")
            continue
    
    db.commit()
    logger.info(f"Saved {fields_saved}/{len(fields)} extracted fields for document {document.id}")
    return fields_saved


def _save_line_items(db: Session, document: Document, line_items: List[Dict[str, Any]]) -> int:
    """
    Save line items to database
    
    Args:
        db: Database session
        document: Document instance
        line_items: List of line items from Azure
        
    Returns:
        Number of line items saved
    """
    items_saved = 0
    
    for item_data in line_items:
        try:
            # Create LineItem instance
            line_item = LineItem(
                document_id=document.id,
                description=item_data.get("description"),
                quantity=item_data.get("quantity"),
                unit_price=item_data.get("unit_price"),
                total=item_data.get("total"),
                confidence=item_data.get("confidence", 0.0)
            )
            
            db.add(line_item)
            items_saved += 1
            
            logger.debug(f"Saved line item: {item_data.get('description', 'N/A')} "
                        f"(qty: {item_data.get('quantity', 0)}, "
                        f"total: {item_data.get('total', 0)}, "
                        f"confidence: {item_data.get('confidence', 0):.2f})")
            
        except Exception as e:
            logger.warning(f"Failed to save line item {item_data.get('description', 'unknown')}: {e}")
            continue
    
    db.commit()
    logger.info(f"Saved {items_saved}/{len(line_items)} line items for document {document.id}")
    return items_saved


def _calculate_overall_confidence(fields: List[Dict[str, Any]], line_items: List[Dict[str, Any]]) -> float:
    """
    Calculate overall confidence score for the document
    
    Args:
        fields: List of extracted fields with confidence scores
        line_items: List of line items with confidence scores
        
    Returns:
        Overall confidence score (0.0 to 1.0)
    """
    all_confidences = []
    
    # Collect field confidences
    for field in fields:
        if "confidence" in field and field["confidence"] is not None:
            all_confidences.append(field["confidence"])
    
    # Collect line item confidences
    for item in line_items:
        if "confidence" in item and item["confidence"] is not None:
            all_confidences.append(item["confidence"])
    
    # Calculate weighted average (give more weight to fields than line items)
    if not all_confidences:
        return 0.0
    
    field_count = len(fields)
    item_count = len(line_items)
    
    if field_count > 0 and item_count > 0:
        # Weighted average: 70% fields, 30% line items
        field_confidences = [f.get("confidence", 0.0) for f in fields if f.get("confidence") is not None]
        item_confidences = [i.get("confidence", 0.0) for i in line_items if i.get("confidence") is not None]
        
        field_avg = sum(field_confidences) / len(field_confidences) if field_confidences else 0.0
        item_avg = sum(item_confidences) / len(item_confidences) if item_confidences else 0.0
        
        overall = (field_avg * 0.7) + (item_avg * 0.3)
    else:
        # Simple average if only one type available
        overall = sum(all_confidences) / len(all_confidences)
    
    return round(overall, 3)


def _update_document_status_failed(db: Session, document_id: str, error_message: str) -> None:
    """
    Update document status to FAILED when processing fails
    
    Args:
        db: Database session (can be None)
        document_id: Document ID
        error_message: Error message to log
    """
    if not db:
        return
    
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = DocumentStatus.FAILED
            document.confidence_score = 0.0
            db.commit()
            logger.info(f"Updated document {document_id} status to FAILED")
        else:
            logger.warning(f"Document {document_id} not found for status update")
    except Exception as e:
        logger.error(f"Failed to update document {document_id} status to FAILED: {e}")
        db.rollback()