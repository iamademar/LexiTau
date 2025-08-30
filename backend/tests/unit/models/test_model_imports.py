"""
Smoke tests to verify all moved models can be imported and instantiated properly.
This ensures the model splitting did not break any imports or basic model functionality.
"""
import pytest
from app.models import ExtractedField, LineItem, FieldCorrection, Client, Project, Category
from app.enums import FileType, DocumentType, DocumentStatus, DocumentClassification
import uuid


class TestModelImports:
    def test_extracted_field_import_and_name(self):
        """Test that ExtractedField model can be imported and has correct __name__"""
        assert ExtractedField.__name__ == "ExtractedField"
        
        # Test basic instantiation (no DB commit)
        field = ExtractedField(
            document_id=uuid.uuid4(),
            field_name="invoice_date",
            value="2024-01-15",
            confidence=0.95
        )
        assert field.field_name == "invoice_date"
        assert field.value == "2024-01-15"
        assert field.confidence == 0.95

    def test_line_item_import_and_name(self):
        """Test that LineItem model can be imported and has correct __name__"""
        assert LineItem.__name__ == "LineItem"
        
        # Test basic instantiation (no DB commit)
        line_item = LineItem(
            document_id=uuid.uuid4(),
            description="Software License",
            quantity=1.0,
            unit_price=99.99,
            total=99.99,
            confidence=0.85
        )
        assert line_item.description == "Software License"
        assert line_item.quantity == 1.0
        assert line_item.unit_price == 99.99

    def test_field_correction_import_and_name(self):
        """Test that FieldCorrection model can be imported and has correct __name__"""
        assert FieldCorrection.__name__ == "FieldCorrection"
        
        # Test basic instantiation (no DB commit)
        correction = FieldCorrection(
            document_id=uuid.uuid4(),
            field_name="vendor_name",
            original_value="Acme Corp",
            corrected_value="ACME Corporation",
            corrected_by=1
        )
        assert correction.field_name == "vendor_name"
        assert correction.original_value == "Acme Corp"
        assert correction.corrected_value == "ACME Corporation"

    def test_client_import_and_name(self):
        """Test that Client model can be imported and has correct __name__"""
        assert Client.__name__ == "Client"
        
        # Test basic instantiation (no DB commit)
        client = Client(
            business_id=1,
            name="Test Client Corp"
        )
        assert client.business_id == 1
        assert client.name == "Test Client Corp"

    def test_project_import_and_name(self):
        """Test that Project model can be imported and has correct __name__"""
        assert Project.__name__ == "Project"
        
        # Test basic instantiation (no DB commit)
        project = Project(
            business_id=1,
            name="Website Redesign"
        )
        assert project.business_id == 1
        assert project.name == "Website Redesign"

    def test_category_import_and_name(self):
        """Test that Category model can be imported and has correct __name__"""
        assert Category.__name__ == "Category"
        
        # Test basic instantiation (no DB commit)
        category = Category(name="Office Supplies")
        assert category.name == "Office Supplies"

    def test_all_models_available_from_package(self):
        """Test that all moved models are available from the main models package"""
        from app.models import (
            ExtractedField, LineItem, FieldCorrection, 
            Client, Project, Category,
            User, Business, Document  # Also test previously moved models
        )
        
        # Verify all models are available and have correct names
        models_to_test = [
            ExtractedField, LineItem, FieldCorrection,
            Client, Project, Category,
            User, Business, Document
        ]
        
        for model in models_to_test:
            assert hasattr(model, '__name__')
            assert hasattr(model, '__tablename__')
            assert model.__name__ in [
                'ExtractedField', 'LineItem', 'FieldCorrection',
                'Client', 'Project', 'Category', 
                'User', 'Business', 'Document'
            ]