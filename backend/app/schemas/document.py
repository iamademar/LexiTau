from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from ..enums import FileType, DocumentType, DocumentStatus, DocumentClassification


class DocumentUploadResult(BaseModel):
    """Result of uploading a single document"""
    success: bool
    filename: str
    document_id: Optional[UUID] = None
    blob_url: Optional[str] = None
    error_message: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[FileType] = None


class DocumentUploadResponse(BaseModel):
    """Response for document upload endpoint"""
    total_files: int
    successful_uploads: int
    failed_uploads: int
    results: List[DocumentUploadResult]


class DocumentBase(BaseModel):
    """Base document schema"""
    filename: str
    file_type: FileType
    document_type: DocumentType
    status: DocumentStatus


class DocumentCreate(DocumentBase):
    """Schema for creating a document"""
    file_url: str
    user_id: int
    business_id: int
    confidence_score: Optional[float] = None


class DocumentResponse(DocumentBase):
    """Schema for document response"""
    id: UUID
    user_id: int
    business_id: int
    file_url: str
    confidence_score: Optional[float] = None
    reviewed_at: Optional[datetime] = Field(None, description="When document was marked as reviewed")
    reviewed_by: Optional[int] = Field(None, description="User ID who reviewed the document")
    is_reviewed: bool = Field(description="True if document has been reviewed")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentFilters(BaseModel):
    """Filters for document listing"""
    status: Optional[DocumentStatus] = None
    document_type: Optional[DocumentType] = None
    classification: Optional[DocumentClassification] = Field(None, description="Filter by document classification (revenue or expense)")
    is_reviewed: Optional[bool] = Field(None, description="Filter by review status (True=reviewed, False=not reviewed)")
    client_id: Optional[int] = Field(None, description="Filter by client ID")
    project_id: Optional[int] = Field(None, description="Filter by project ID")  
    category_id: Optional[int] = Field(None, description="Filter by category ID")
    
    
class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")


class DocumentListResponse(BaseModel):
    """Paginated response for document listing"""
    documents: List[DocumentResponse]
    pagination: PaginationMeta


class ExtractedFieldResponse(BaseModel):
    """Response schema for extracted fields"""
    id: int
    field_name: str
    value: Optional[str] = None
    original_value: Optional[str] = Field(None, description="Original OCR-extracted value before any corrections")
    corrected_value: Optional[str] = Field(None, description="User-corrected value, if any corrections were made")
    confidence: Optional[float] = None
    is_low_confidence: bool = Field(description="True if confidence < 0.7")
    is_corrected: bool = Field(description="True if field has been corrected by user")
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LineItemResponse(BaseModel):
    """Response schema for line items"""
    id: int
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None
    confidence: Optional[float] = None
    is_low_confidence: bool = Field(description="True if confidence < 0.7")
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentFieldsResponse(BaseModel):
    """Response schema for document fields endpoint"""
    document_id: UUID
    document_info: DocumentResponse
    extracted_fields: List[ExtractedFieldResponse]
    line_items: List[LineItemResponse]
    processing_status: DocumentStatus
    overall_confidence: Optional[float] = None
    fields_summary: dict = Field(description="Summary statistics for extracted fields")
    line_items_summary: dict = Field(description="Summary statistics for line items")


class FieldCorrectionRequest(BaseModel):
    """Single field correction request"""
    field_name: str = Field(min_length=1, description="Name of the field to correct")
    corrected_value: str = Field(description="The corrected value for the field")


class FieldCorrectionsRequest(BaseModel):
    """Request schema for field corrections"""
    corrections: List[FieldCorrectionRequest] = Field(min_length=1, description="List of field corrections to apply")


class FieldCorrectionResult(BaseModel):
    """Result of a single field correction"""
    field_name: str
    success: bool
    message: str
    original_value: Optional[str] = None
    corrected_value: str
    was_new_field: bool = Field(description="True if field didn't exist and was created")


class FieldCorrectionsResponse(BaseModel):
    """Response schema for field corrections endpoint"""
    document_id: UUID
    corrections_applied: int
    corrections_failed: int
    results: List[FieldCorrectionResult]
    updated_fields: List[ExtractedFieldResponse] = Field(description="All fields after corrections applied")


class LineItemUpdateRequest(BaseModel):
    """Request schema for updating a line item"""
    description: Optional[str] = Field(None, description="Product/service description")
    quantity: Optional[Decimal] = Field(None, ge=0, description="Quantity (must be non-negative)")
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Unit price (must be non-negative)")
    total: Optional[Decimal] = Field(None, ge=0, description="Total amount (must be non-negative)")


class LineItemUpdateResponse(BaseModel):
    """Response schema for line item update endpoint"""
    success: bool
    message: str
    line_item: LineItemResponse = Field(description="Updated line item data")
    document_id: UUID


class MarkReviewedRequest(BaseModel):
    """Request schema for marking document as reviewed (optional request body)"""
    pass  # No required fields - marking as reviewed just sets timestamp and user


class MarkReviewedResponse(BaseModel):
    """Response schema for mark reviewed endpoint"""
    success: bool
    message: str
    document_id: UUID
    reviewed_at: datetime
    reviewed_by: int = Field(description="User ID who marked document as reviewed")


class DocumentTagRequest(BaseModel):
    """Request schema for tagging a document"""
    client_id: Optional[int] = Field(None, description="ID of client to associate with document")
    project_id: Optional[int] = Field(None, description="ID of project to associate with document")  
    category_id: Optional[int] = Field(None, description="ID of category to associate with document")


class DocumentTagResponse(BaseModel):
    """Response schema for document tagging endpoint"""
    success: bool
    message: str
    document_id: UUID
    client_id: Optional[int] = None
    project_id: Optional[int] = None
    category_id: Optional[int] = None
    updated_at: datetime