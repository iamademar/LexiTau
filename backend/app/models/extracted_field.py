from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base


class ExtractedField(Base):
    """
    Stores extracted fields from document OCR processing.
    Each field represents a specific piece of information extracted from the document
    (e.g., invoice_date, vendor_name, total_amount) along with confidence scores.
    """
    __tablename__ = "extracted_fields"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)  # e.g., "invoice_date", "vendor_name", "total_amount"
    value = Column(Text, nullable=True)  # The extracted value as text
    confidence = Column(Float, nullable=True)  # Confidence score (0.0 to 1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    document = relationship("Document", back_populates="extracted_fields")