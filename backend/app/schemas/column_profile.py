from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class ColumnProfileBase(BaseModel):
    """Base column profile schema"""
    database_name: str = Field(description="Database name")
    table_name: str = Field(description="Table name")
    column_name: str = Field(description="Column name")
    data_type: str = Field(description="SQL data type")
    table_row_count: int = Field(ge=0, description="Total number of rows in the table")
    null_count: int = Field(ge=0, description="Number of NULL values")
    non_null_count: int = Field(ge=0, description="Number of non-NULL values")
    distinct_count: Optional[Decimal] = Field(None, description="Number of distinct values")


class ColumnProfileCreate(ColumnProfileBase):
    """Schema for creating a column profile"""
    # Shape information
    min_value: Optional[str] = Field(None, description="Minimum value as string")
    max_value: Optional[str] = Field(None, description="Maximum value as string")
    length_min: Optional[int] = Field(None, description="Minimum string length")
    length_max: Optional[int] = Field(None, description="Maximum string length")
    char_classes: Optional[Dict[str, Any]] = Field(None, description="Character class counts")
    common_prefixes: Optional[List[Dict[str, Any]]] = Field(None, description="Most common prefixes")
    
    # Value samples
    top_k_values: Optional[List[Dict[str, Any]]] = Field(None, description="Top K most frequent values")
    distinct_sample: Optional[List[str]] = Field(None, description="Sample of distinct values")
    minhash_signature: Optional[List[int]] = Field(None, description="MinHash signature for similarity")
    
    # Generated descriptions
    english_description: Optional[str] = Field(None, description="Human-readable description")
    short_summary: Optional[str] = Field(None, description="LLM-generated short summary")
    long_summary: Optional[str] = Field(None, description="Detailed long summary")
    vector_embedding: Optional[List[float]] = Field(None, description="Vector embedding from summary")
    
    generated_at: datetime = Field(description="When the profile was generated")


class ColumnProfileResponse(ColumnProfileBase):
    """Schema for column profile response"""
    id: int = Field(description="Unique profile ID")
    
    # Shape information
    min_value: Optional[str] = Field(None, description="Minimum value as string")
    max_value: Optional[str] = Field(None, description="Maximum value as string")
    length_min: Optional[int] = Field(None, description="Minimum string length")
    length_max: Optional[int] = Field(None, description="Maximum string length")
    char_classes: Optional[Dict[str, Any]] = Field(None, description="Character class counts")
    common_prefixes: Optional[List[Dict[str, Any]]] = Field(None, description="Most common prefixes")
    
    # Value samples
    top_k_values: Optional[List[Dict[str, Any]]] = Field(None, description="Top K most frequent values")
    distinct_sample: Optional[List[str]] = Field(None, description="Sample of distinct values")
    minhash_signature: Optional[List[int]] = Field(None, description="MinHash signature for similarity")
    
    # Generated descriptions
    english_description: Optional[str] = Field(None, description="Human-readable description")
    short_summary: Optional[str] = Field(None, description="LLM-generated short summary")
    long_summary: Optional[str] = Field(None, description="Detailed long summary")
    vector_embedding: Optional[List[float]] = Field(None, description="Vector embedding from summary")
    
    # Metadata
    generated_at: datetime = Field(description="When the profile was generated")
    created_at: datetime = Field(description="When the record was created")
    updated_at: Optional[datetime] = Field(None, description="When the record was last updated")

    class Config:
        from_attributes = True


class ColumnProfileFilters(BaseModel):
    """Filters for column profile listing"""
    database_name: Optional[str] = Field(None, description="Filter by database name")
    table_name: Optional[str] = Field(None, description="Filter by table name")
    column_name: Optional[str] = Field(None, description="Filter by column name")
    data_type: Optional[str] = Field(None, description="Filter by data type")


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")


class ColumnProfileListResponse(BaseModel):
    """Paginated response for column profile listing"""
    profiles: List[ColumnProfileResponse]
    pagination: PaginationMeta


class ColumnProfileSimilarityRequest(BaseModel):
    """Request schema for finding similar columns"""
    profile_id: int = Field(description="ID of the column profile to find similarities for")
    similarity_threshold: float = Field(ge=0.0, le=1.0, default=0.8, description="Similarity threshold (0-1)")
    limit: int = Field(ge=1, le=100, default=10, description="Maximum number of similar columns to return")


class ColumnProfileSimilarityResponse(BaseModel):
    """Response schema for column similarity search"""
    query_profile: ColumnProfileResponse = Field(description="The original column profile")
    similar_profiles: List[ColumnProfileResponse] = Field(description="Similar column profiles")
    similarities: List[float] = Field(description="Similarity scores corresponding to similar_profiles")