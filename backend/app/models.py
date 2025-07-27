from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .db import Base
from .enums import FileType, DocumentType, DocumentStatus

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
    documents = relationship("Document", back_populates="user")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_url = Column(String, nullable=False)  # Azure Blob URL
    file_type = Column(Enum(FileType), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.PENDING)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="documents")
    business = relationship("Business")