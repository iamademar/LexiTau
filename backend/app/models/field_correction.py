from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..db import Base


class FieldCorrection(Base):
    """
    Tracks user corrections to extracted field values.
    Maintains audit trail of all field corrections made by users to improve
    future OCR accuracy and provide data quality insights.
    """
    __tablename__ = "field_corrections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)  # Same as ExtractedField.field_name
    original_value = Column(Text, nullable=True)  # Original extracted value
    corrected_value = Column(Text, nullable=False)  # User-corrected value
    corrected_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who made the correction
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # When correction was made
    
    # Relationships
    document = relationship("Document", back_populates="field_corrections")
    corrected_by_user = relationship("User", back_populates="field_corrections")