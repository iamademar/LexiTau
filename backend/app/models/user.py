from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base

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