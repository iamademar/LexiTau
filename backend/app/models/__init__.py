# Import and re-export all models for backward compatibility
# This maintains the same public API while enabling the layer-based structure

# Import Base from db module
from ..db import Base

# Import all models from their individual files
from .user import User
from .business import Business
from .document import Document
from .extracted_field import ExtractedField
from .line_item import LineItem
from .field_correction import FieldCorrection
from .client import Client
from .project import Project
from .category import Category
from .column_profile import ColumnProfile

# Ensure all models are available at package level
__all__ = [
    "Base",
    "User",
    "Business", 
    "Document",
    "ExtractedField",
    "LineItem",
    "FieldCorrection",
    "Client",
    "Project",
    "Category",
    "ColumnProfile"
]