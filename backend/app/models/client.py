from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base


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