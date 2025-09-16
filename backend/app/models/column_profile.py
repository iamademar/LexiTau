from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, UniqueConstraint
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from ..db import Base
from ..types import JSONBCompat as JSONB


class ColumnProfile(Base):
    __tablename__ = "column_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    database_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(100), nullable=False)
    table_row_count = Column(Integer, nullable=False)
    null_count = Column(Integer, nullable=False)
    non_null_count = Column(Integer, nullable=False)
    distinct_count = Column(Numeric, nullable=True)
    
    # Shape information
    min_value = Column(Text, nullable=True)
    max_value = Column(Text, nullable=True)
    length_min = Column(Integer, nullable=True)
    length_max = Column(Integer, nullable=True)
    char_classes = Column(JSONB, nullable=True)
    common_prefixes = Column(JSONB, nullable=True)
    
    # Value samples
    top_k_values = Column(JSONB, nullable=True)
    distinct_sample = Column(JSONB, nullable=True)
    minhash_signature = Column(JSONB, nullable=True)
    
    # Generated descriptions (3 levels as per paper)
    english_description = Column(Text, nullable=True)
    short_summary = Column(Text, nullable=True)
    long_summary = Column(Text, nullable=True)
    vector_embedding = Column(Vector(1536), nullable=True)
    
    # Metadata
    generated_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('database_name', 'table_name', 'column_name', name='unique_column_profile'),
    )