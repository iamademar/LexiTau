"""
Legacy models.py file - All models have been moved to individual files.

All SQLAlchemy models are now organized in the models/ directory:
- models/user.py - User model
- models/business.py - Business model  
- models/document.py - Document model
- models/extracted_field.py - ExtractedField model
- models/line_item.py - LineItem model
- models/field_correction.py - FieldCorrection model
- models/client.py - Client model
- models/project.py - Project model
- models/category.py - Category model

All models are re-exported through models/__init__.py for backward compatibility.
Import using: from app.models import ModelName or from app import models; models.ModelName
"""

# This file is kept for compatibility with any direct imports,
# but all actual model definitions have been moved to individual files
# in the models/ directory and are imported through models/__init__.py