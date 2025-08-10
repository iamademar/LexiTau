from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from ..enums import FileType, DocumentType, DocumentStatus


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
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentFilters(BaseModel):
    """Filters for document listing"""
    status: Optional[DocumentStatus] = None
    document_type: Optional[DocumentType] = None
    
    
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
    confidence: Optional[float] = None
    is_low_confidence: bool = Field(description="True if confidence < 0.7")
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