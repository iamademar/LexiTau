"""
OCR Processing Tasks

This module contains legacy placeholder functions.
Actual Celery tasks have been moved to document_tasks.py
"""

import uuid
import logging
from app.tasks.document_tasks import dispatch_ocr_task as _dispatch_ocr_task

logger = logging.getLogger(__name__)


def dispatch_ocr_task(document_id: uuid.UUID) -> str:
    """
    Legacy function that now delegates to actual Celery implementation
    
    Args:
        document_id: UUID of the document to process
        
    Returns:
        Task ID for tracking
    """
    return _dispatch_ocr_task(document_id)