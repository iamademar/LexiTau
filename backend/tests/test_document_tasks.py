"""
Tests for C3 - OCR Celery Task with Azure Form Recognizer integration
"""

import pytest
import uuid
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

from app.tasks.document_tasks import (
    process_document_ocr, 
    _save_extracted_fields, 
    _save_line_items, 
    _calculate_overall_confidence,
    _update_document_status_failed
)
from app.models import Document, ExtractedField, LineItem, User, Business
from app.enums import DocumentStatus, DocumentType, FileType
from app.auth import create_user_and_business
from app.test_db import get_test_db, create_test_tables, drop_test_tables


@pytest.fixture(scope="module")
def setup_database():
    create_test_tables()
    yield
    drop_test_tables()


@pytest.fixture
def db_session(setup_database):
    db = next(get_test_db())
    try:
        yield db
    finally:
        # Clean up test data
        db.query(LineItem).delete()
        db.query(ExtractedField).delete()
        db.query(Document).delete()
        db.query(User).delete()
        db.query(Business).delete()
        db.commit()
        db.close()


@pytest.fixture
def test_user_and_document(db_session):
    """Create test user, business and document"""
    # Create user and business
    user = create_user_and_business(
        db=db_session,
        email="test_c3@example.com",
        password="testpass123",
        business_name="C3 Test Business"
    )
    
    # Create test document
    document = Document(
        user_id=user.id,
        business_id=user.business_id,
        filename="test_invoice_c3.pdf",
        file_url="https://example.com/test_invoice_c3.pdf",
        file_type=FileType.PDF,
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.PROCESSING,
        confidence_score=None
    )
    
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    return user, document


class TestProcessDocumentOCR:
    """Test cases for process_document_ocr Celery task"""
    
    @patch('app.tasks.document_tasks.get_db')
    @patch('app.tasks.document_tasks.get_azure_form_recognizer_client')
    def test_process_document_ocr_success_invoice(self, mock_get_client, mock_get_db, test_user_and_document):
        """Test successful OCR processing for invoice"""
        user, document = test_user_and_document
        db_session = mock_get_db.return_value.__next__.return_value
        db_session.query.return_value.filter.return_value.first.return_value = document
        
        # Mock Azure Form Recognizer response
        mock_client = mock_get_client.return_value
        mock_extraction_result = {
            "fields": [
                {
                    "field_name": "vendor_name",
                    "value": "ABC Services Ltd",
                    "confidence": 0.95
                },
                {
                    "field_name": "invoice_number", 
                    "value": "INV-2024-001",
                    "confidence": 0.92
                },
                {
                    "field_name": "total_amount",
                    "value": "1250.00",
                    "confidence": 0.99
                },
                {
                    "field_name": "invoice_date",
                    "value": "2024-08-03",
                    "confidence": 0.97
                }
            ],
            "line_items": [
                {
                    "description": "Lawn Maintenance Service",
                    "quantity": Decimal("1.0"),
                    "unit_price": Decimal("750.00"),
                    "total": Decimal("750.00"),
                    "confidence": 0.94
                },
                {
                    "description": "Tree Trimming",
                    "quantity": Decimal("2.0"),
                    "unit_price": Decimal("250.00"),
                    "total": Decimal("500.00"),
                    "confidence": 0.93
                }
            ]
        }
        
        # Mock the async extract_fields method
        async def mock_extract_fields(*args, **kwargs):
            return mock_extraction_result
        
        mock_client.extract_fields = mock_extract_fields
        
        # Run the task
        result = process_document_ocr(str(document.id))
        
        # Verify results
        assert result["status"] == "completed"
        assert result["document_id"] == str(document.id)
        assert result["fields_extracted"] == 4
        assert result["line_items_extracted"] == 2
        assert result["document_type"] == "INVOICE"
        assert 0.9 <= result["overall_confidence"] <= 1.0
        
        # Verify document status was updated
        assert document.status == DocumentStatus.COMPLETED
        assert document.confidence_score is not None
        assert document.confidence_score > 0.9
    
    @patch('app.tasks.document_tasks.get_db')
    @patch('app.tasks.document_tasks.get_azure_form_recognizer_client')
    def test_process_document_ocr_success_receipt(self, mock_get_client, mock_get_db, test_user_and_document):
        """Test successful OCR processing for receipt"""
        user, document = test_user_and_document
        document.document_type = DocumentType.RECEIPT
        
        db_session = mock_get_db.return_value.__next__.return_value
        db_session.query.return_value.filter.return_value.first.return_value = document
        
        # Mock Azure Form Recognizer response for receipt
        mock_client = mock_get_client.return_value
        mock_extraction_result = {
            "fields": [
                {
                    "field_name": "merchant_name",
                    "value": "Home Depot",
                    "confidence": 0.98
                },
                {
                    "field_name": "transaction_date",
                    "value": "2024-08-03",
                    "confidence": 0.96
                },
                {
                    "field_name": "total_amount",
                    "value": "85.50",
                    "confidence": 0.99
                }
            ],
            "line_items": [
                {
                    "description": "Garden Hose 50ft",
                    "quantity": Decimal("1.0"),
                    "unit_price": Decimal("29.99"),
                    "total": Decimal("29.99"),
                    "confidence": 0.97
                }
            ]
        }
        
        async def mock_extract_fields(*args, **kwargs):
            return mock_extraction_result
        
        mock_client.extract_fields = mock_extract_fields
        
        # Run the task
        result = process_document_ocr(str(document.id))
        
        # Verify results
        assert result["status"] == "completed"
        assert result["fields_extracted"] == 3
        assert result["line_items_extracted"] == 1
        assert result["document_type"] == "RECEIPT"
        assert result["overall_confidence"] > 0.95
    
    @patch('app.tasks.document_tasks.get_db')
    def test_process_document_ocr_document_not_found(self, mock_get_db):
        """Test task handling when document is not found"""
        db_session = mock_get_db.return_value.__next__.return_value
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test that ValueError is raised for missing document
        with pytest.raises(ValueError, match="Document .* not found"):
            # Call the task function directly to avoid Celery complexity
            process_document_ocr(str(uuid.uuid4()))
    
    @patch('app.tasks.document_tasks.get_db')
    @patch('app.tasks.document_tasks.get_azure_form_recognizer_client')
    def test_process_document_ocr_azure_error(self, mock_get_client, mock_get_db, test_user_and_document):
        """Test task handling when Azure API fails"""
        user, document = test_user_and_document
        
        db_session = mock_get_db.return_value.__next__.return_value
        db_session.query.return_value.filter.return_value.first.return_value = document
        
        # Mock Azure client to raise an error
        from app.services.azure_form_recognizer import DocumentExtractionError
        mock_client = mock_get_client.return_value
        
        async def mock_extract_fields_error(*args, **kwargs):
            raise DocumentExtractionError("Azure API error")
        
        mock_client.extract_fields = mock_extract_fields_error
        
        # Test that DocumentExtractionError is raised
        with pytest.raises(DocumentExtractionError, match="Azure API error"):
            # Call the task function directly
            process_document_ocr(str(document.id))


class TestHelperFunctions:
    """Test cases for helper functions"""
    
    def test_save_extracted_fields(self, db_session, test_user_and_document):
        """Test saving extracted fields to database"""
        user, document = test_user_and_document
        
        fields_data = [
            {
                "field_name": "vendor_name",
                "value": "Test Vendor",
                "confidence": 0.95
            },
            {
                "field_name": "total_amount",
                "value": "1000.00",
                "confidence": 0.99
            }
        ]
        
        saved_count = _save_extracted_fields(db_session, document, fields_data)
        
        assert saved_count == 2
        
        # Verify fields were saved
        saved_fields = db_session.query(ExtractedField).filter(
            ExtractedField.document_id == document.id
        ).all()
        
        assert len(saved_fields) == 2
        field_names = {f.field_name for f in saved_fields}
        assert field_names == {"vendor_name", "total_amount"}
        
        vendor_field = next(f for f in saved_fields if f.field_name == "vendor_name")
        assert vendor_field.value == "Test Vendor"
        assert vendor_field.confidence == 0.95
    
    def test_save_line_items(self, db_session, test_user_and_document):
        """Test saving line items to database"""
        user, document = test_user_and_document
        
        line_items_data = [
            {
                "description": "Service A",
                "quantity": Decimal("1.0"),
                "unit_price": Decimal("500.00"),
                "total": Decimal("500.00"),
                "confidence": 0.94
            },
            {
                "description": "Service B",
                "quantity": Decimal("2.0"),
                "unit_price": Decimal("250.00"),
                "total": Decimal("500.00"),
                "confidence": 0.92
            }
        ]
        
        saved_count = _save_line_items(db_session, document, line_items_data)
        
        assert saved_count == 2
        
        # Verify line items were saved
        saved_items = db_session.query(LineItem).filter(
            LineItem.document_id == document.id
        ).all()
        
        assert len(saved_items) == 2
        
        service_a = next(i for i in saved_items if i.description == "Service A")
        assert service_a.quantity == Decimal("1.0")
        assert service_a.unit_price == Decimal("500.00")
        assert service_a.total == Decimal("500.00")
        assert service_a.confidence == 0.94
    
    def test_calculate_overall_confidence(self):
        """Test overall confidence calculation"""
        fields = [
            {"confidence": 0.95},
            {"confidence": 0.90},
            {"confidence": 0.98}
        ]
        
        line_items = [
            {"confidence": 0.92},
            {"confidence": 0.88}
        ]
        
        # Test with both fields and line items (70% fields, 30% line items)
        confidence = _calculate_overall_confidence(fields, line_items)
        expected = (0.943 * 0.7) + (0.9 * 0.3)  # 0.943 = (0.95+0.90+0.98)/3
        assert abs(confidence - expected) < 0.01
        
        # Test with only fields
        confidence_fields_only = _calculate_overall_confidence(fields, [])
        expected_fields = (0.95 + 0.90 + 0.98) / 3
        assert abs(confidence_fields_only - expected_fields) < 0.01
        
        # Test with empty inputs
        confidence_empty = _calculate_overall_confidence([], [])
        assert confidence_empty == 0.0
    
    def test_update_document_status_failed(self, db_session, test_user_and_document):
        """Test updating document status to FAILED"""
        user, document = test_user_and_document
        
        # Verify initial status
        assert document.status == DocumentStatus.PROCESSING
        
        _update_document_status_failed(db_session, str(document.id), "Test error")
        
        # Refresh document from database
        db_session.refresh(document)
        
        assert document.status == DocumentStatus.FAILED
        assert document.confidence_score == 0.0


class TestTaskIntegration:
    """Integration tests for the OCR task"""
    
    @patch('app.tasks.document_tasks.get_azure_form_recognizer_client')
    def test_ocr_task_with_real_database(self, mock_get_client, db_session):
        """Test OCR task with real database operations"""
        # Create test data
        user = create_user_and_business(
            db=db_session,
            email="integration_test@example.com",
            password="testpass123",
            business_name="Integration Test Business"
        )
        
        document = Document(
            user_id=user.id,
            business_id=user.business_id,
            filename="integration_test.pdf",
            file_url="https://example.com/integration_test.pdf",
            file_type=FileType.PDF,
            document_type=DocumentType.INVOICE,
            status=DocumentStatus.PROCESSING
        )
        
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Mock Azure response
        mock_client = mock_get_client.return_value
        mock_extraction_result = {
            "fields": [
                {
                    "field_name": "invoice_number",
                    "value": "TEST-001",
                    "confidence": 0.95
                }
            ],
            "line_items": [
                {
                    "description": "Test Service",
                    "quantity": Decimal("1.0"),
                    "unit_price": Decimal("100.00"),
                    "total": Decimal("100.00"),
                    "confidence": 0.90
                }
            ]
        }
        
        async def mock_extract_fields(*args, **kwargs):
            return mock_extraction_result
        
        mock_client.extract_fields = mock_extract_fields
        
        # Mock get_db to return our test session
        with patch('app.tasks.document_tasks.get_db') as mock_get_db:
            mock_get_db.return_value.__next__.return_value = db_session
            
            # Run the task function directly
            result = process_document_ocr(str(document.id))
        
        # Verify task result
        assert result["status"] == "completed"
        assert result["fields_extracted"] == 1
        assert result["line_items_extracted"] == 1
        
        # Since the task uses a different db session, query for the document again
        updated_doc = db_session.query(Document).filter(Document.id == document.id).first()
        assert updated_doc.status == DocumentStatus.COMPLETED
        assert updated_doc.confidence_score > 0.9
        
        # Verify extracted fields were saved
        extracted_fields = db_session.query(ExtractedField).filter(
            ExtractedField.document_id == document.id
        ).all()
        assert len(extracted_fields) == 1
        assert extracted_fields[0].field_name == "invoice_number"
        assert extracted_fields[0].value == "TEST-001"
        
        # Verify line items were saved
        line_items = db_session.query(LineItem).filter(
            LineItem.document_id == document.id
        ).all()
        assert len(line_items) == 1
        assert line_items[0].description == "Test Service"
        assert line_items[0].total == Decimal("100.00")