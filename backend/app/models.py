from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float, Enum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .db import Base
from .enums import FileType, DocumentType, DocumentStatus, DocumentClassification

class Business(Base):
    __tablename__ = "businesses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    users = relationship("User", back_populates="business")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    business = relationship("Business", back_populates="users")
    documents = relationship("Document", back_populates="user", foreign_keys="Document.user_id")
    field_corrections = relationship("FieldCorrection", back_populates="corrected_by_user")

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


class ExtractedField(Base):
    """
    Stores extracted fields from document OCR processing.
    Each field represents a specific piece of information extracted from the document
    (e.g., invoice_date, vendor_name, total_amount) along with confidence scores.
    """
    __tablename__ = "extracted_fields"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)  # e.g., "invoice_date", "vendor_name", "total_amount"
    value = Column(Text, nullable=True)  # The extracted value as text
    confidence = Column(Float, nullable=True)  # Confidence score (0.0 to 1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    document = relationship("Document", back_populates="extracted_fields")


class LineItem(Base):
    """
    Stores individual line items extracted from invoices and receipts.
    Each line item represents a product or service with quantity, price, and total.
    """
    __tablename__ = "line_items"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    description = Column(Text, nullable=True)  # Product/service description
    quantity = Column(Numeric(10, 3), nullable=True)  # Quantity (supports decimals like 1.5 hours)
    unit_price = Column(Numeric(10, 2), nullable=True)  # Price per unit in currency
    total = Column(Numeric(10, 2), nullable=True)  # Total amount for this line item
    confidence = Column(Float, nullable=True)  # Confidence score (0.0 to 1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    document = relationship("Document", back_populates="line_items")


class FieldCorrection(Base):
    """
    Tracks user corrections to extracted field values.
    Maintains audit trail of all field corrections made by users to improve
    future OCR accuracy and provide data quality insights.
    """
    __tablename__ = "field_corrections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)  # Same as ExtractedField.field_name
    original_value = Column(Text, nullable=True)  # Original extracted value
    corrected_value = Column(Text, nullable=False)  # User-corrected value
    corrected_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who made the correction
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # When correction was made
    
    # Relationships
    document = relationship("Document", back_populates="field_corrections")
    corrected_by_user = relationship("User", back_populates="field_corrections")


class Client(Base):
    """
    Represents clients that businesses work with.
    Each client is associated with a specific business for multi-tenant isolation.
    """
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    business = relationship("Business")


class Project(Base):
    """
    Represents projects that businesses work on.
    Each project is associated with a specific business for multi-tenant isolation.
    """
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    business = relationship("Business")


class Category(Base):
    """
    Represents expense/revenue categories for document classification.
    Categories are global and shared across all businesses.
    """
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())