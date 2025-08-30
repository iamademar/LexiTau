from sqlalchemy import Column, Integer, DateTime, Text, Float, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base


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