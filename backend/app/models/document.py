from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..db import Base
from ..enums import FileType, DocumentType, DocumentStatus, DocumentClassification


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    filename = Column(String, nullable=False)
    file_url = Column(String, nullable=False)  # Azure Blob URL
    file_type = Column(Enum(FileType), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    classification = Column(Enum(DocumentClassification), nullable=False, index=True)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.PENDING)
    confidence_score = Column(Float, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="documents", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by], post_update=True)
    business = relationship("Business")
    client = relationship("Client")
    project = relationship("Project")
    category = relationship("Category")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")
    line_items = relationship("LineItem", back_populates="document", cascade="all, delete-orphan")
    field_corrections = relationship("FieldCorrection", back_populates="document", cascade="all, delete-orphan")