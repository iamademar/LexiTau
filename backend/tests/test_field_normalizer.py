"""
Tests for field normalization utilities.
Tests mapping Azure Document Intelligence output to internal field keys and handling of missing/null values.
"""

import pytest
from decimal import Decimal
from datetime import date, datetime

from app.services.field_normalizer import (
    normalize_invoice_fields,
    normalize_receipt_fields,
    normalize_line_items,
    _normalize_field_value,
    get_field_confidence_summary
)


class TestNormalizeInvoiceFields:
    """Test invoice field normalization"""
    
    def test_normalize_complete_invoice_fields(self):
        """Test normalization with all fields present"""
        azure_fields = [
            {"field_name": "vendor_name", "value": "ACME Corporation", "confidence": 0.95},
            {"field_name": "vendor_address", "value": "123 Main St, City, State 12345", "confidence": 0.88},
            {"field_name": "invoice_number", "value": "INV-001", "confidence": 0.92},
            {"field_name": "invoice_date", "value": "2024-01-15", "confidence": 0.90},
            {"field_name": "due_date", "value": "2024-02-15", "confidence": 0.89},
            {"field_name": "subtotal", "value": "1000.00", "confidence": 0.94},
            {"field_name": "tax_amount", "value": "80.00", "confidence": 0.91},
            {"field_name": "total_amount", "value": "1080.00", "confidence": 0.96}
        ]
        
        result = normalize_invoice_fields(azure_fields)
        
        # Check structure
        assert isinstance(result, dict)
        assert len(result) == 15  # All possible invoice fields
        
        # Check specific fields
        assert result["vendor_name"]["value"] == "ACME Corporation"
        assert result["vendor_name"]["confidence"] == 0.95
        assert result["vendor_name"]["raw_value"] == "ACME Corporation"
        
        assert result["invoice_number"]["value"] == "INV-001"
        assert result["invoice_date"]["value"] == date(2024, 1, 15)
        
        # Check decimal fields
        assert result["subtotal"]["value"] == Decimal("1000.00")
        assert result["tax_amount"]["value"] == Decimal("80.00")
        assert result["total_amount"]["value"] == Decimal("1080.00")
        
        # Check missing fields
        assert result["customer_name"]["value"] is None
        assert result["customer_name"]["confidence"] == 0.0
        assert result["customer_name"]["raw_value"] == ""

    def test_normalize_empty_invoice_fields(self):
        """Test normalization with empty input"""
        result = normalize_invoice_fields([])
        assert result == {}
        
        result = normalize_invoice_fields(None)
        assert result == {}

    def test_normalize_invoice_fields_with_nulls(self):
        """Test normalization with null/empty values"""
        azure_fields = [
            {"field_name": "vendor_name", "value": "", "confidence": 0.0},
            {"field_name": "invoice_number", "value": None, "confidence": 0.0},
            {"field_name": "total_amount", "value": "500.50", "confidence": 0.85}
        ]
        
        result = normalize_invoice_fields(azure_fields)
        
        assert result["vendor_name"]["value"] is None
        assert result["invoice_number"]["value"] is None
        assert result["total_amount"]["value"] == Decimal("500.50")

    def test_normalize_invoice_fields_invalid_decimals(self):
        """Test normalization with invalid decimal values"""
        azure_fields = [
            {"field_name": "subtotal", "value": "not-a-number", "confidence": 0.8},
            {"field_name": "tax_amount", "value": "$invalid$", "confidence": 0.7},
            {"field_name": "total_amount", "value": "1,234.56", "confidence": 0.9}
        ]
        
        result = normalize_invoice_fields(azure_fields)
        
        assert result["subtotal"]["value"] is None
        assert result["tax_amount"]["value"] is None
        assert result["total_amount"]["value"] == Decimal("1234.56")  # Commas should be cleaned


class TestNormalizeReceiptFields:
    """Test receipt field normalization"""
    
    def test_normalize_complete_receipt_fields(self):
        """Test normalization with all fields present"""
        azure_fields = [
            {"field_name": "merchant_name", "value": "Best Buy", "confidence": 0.97},
            {"field_name": "merchant_address", "value": "456 Tech Ave, Silicon Valley, CA", "confidence": 0.85},
            {"field_name": "merchant_phone", "value": "(555) 123-4567", "confidence": 0.88},
            {"field_name": "transaction_date", "value": "2024-01-20", "confidence": 0.93},
            {"field_name": "transaction_time", "value": "14:30:00", "confidence": 0.89},
            {"field_name": "subtotal", "value": "299.99", "confidence": 0.95},
            {"field_name": "tax_amount", "value": "24.00", "confidence": 0.92},
            {"field_name": "total_amount", "value": "323.99", "confidence": 0.98},
            {"field_name": "tip_amount", "value": "0.00", "confidence": 0.90}
        ]
        
        result = normalize_receipt_fields(azure_fields)
        
        # Check structure
        assert isinstance(result, dict)
        assert len(result) == 10  # All possible receipt fields
        
        # Check specific fields
        assert result["merchant_name"]["value"] == "Best Buy"
        assert result["merchant_name"]["confidence"] == 0.97
        
        assert result["merchant_phone"]["value"] == "(555) 123-4567"
        assert result["transaction_time"]["value"] == "14:30:00"
        
        # Check decimal fields
        assert result["subtotal"]["value"] == Decimal("299.99")
        assert result["tax_amount"]["value"] == Decimal("24.00")
        assert result["total_amount"]["value"] == Decimal("323.99")
        assert result["tip_amount"]["value"] == Decimal("0.00")

    def test_normalize_empty_receipt_fields(self):
        """Test normalization with empty input"""
        result = normalize_receipt_fields([])
        assert result == {}
        
        result = normalize_receipt_fields(None)
        assert result == {}

    def test_normalize_receipt_fields_partial(self):
        """Test normalization with only some fields present"""
        azure_fields = [
            {"field_name": "merchant_name", "value": "Coffee Shop", "confidence": 0.92},
            {"field_name": "total_amount", "value": "15.75", "confidence": 0.96}
        ]
        
        result = normalize_receipt_fields(azure_fields)
        
        assert result["merchant_name"]["value"] == "Coffee Shop"
        assert result["total_amount"]["value"] == Decimal("15.75")
        assert result["merchant_address"]["value"] is None
        assert result["tax_amount"]["value"] is None


class TestNormalizeLineItems:
    """Test line item normalization"""
    
    def test_normalize_invoice_line_items(self):
        """Test normalization of invoice line items"""
        azure_line_items = [
            {
                "description": "Widget A",
                "quantity": 2,
                "unit_price": "25.00",
                "total": "50.00",
                "confidence": 0.95
            },
            {
                "description": "Service Fee",
                "quantity": 1,
                "unit_price": "10.00",
                "total": "10.00",
                "confidence": 0.88
            }
        ]
        
        result = normalize_line_items(azure_line_items, "invoice")
        
        assert len(result) == 2
        
        # Check first item
        item1 = result[0]
        assert item1["line_number"] == 1
        assert item1["description"] == "Widget A"
        assert item1["quantity"] == Decimal("2")
        assert item1["unit_price"] == Decimal("25.00")
        assert item1["total"] == Decimal("50.00")
        assert item1["confidence"] == 0.95
        
        # Check second item
        item2 = result[1]
        assert item2["line_number"] == 2
        assert item2["description"] == "Service Fee"
        assert item2["quantity"] == Decimal("1")

    def test_normalize_line_items_empty(self):
        """Test normalization with empty line items"""
        result = normalize_line_items([])
        assert result == []
        
        result = normalize_line_items(None)
        assert result == []

    def test_normalize_line_items_missing_data(self):
        """Test normalization with missing data in line items"""
        azure_line_items = [
            {
                "description": "Unknown Item",
                "confidence": 0.75
                # Missing quantity, unit_price, total
            },
            {
                "total": "100.00",
                "confidence": 0.90
                # Missing description, quantity, unit_price
            }
        ]
        
        result = normalize_line_items(azure_line_items)
        
        assert len(result) == 2
        
        # First item - has description
        assert result[0]["description"] == "Unknown Item"
        assert result[0]["quantity"] == Decimal("1")  # Default quantity
        assert result[0]["unit_price"] is None
        assert result[0]["total"] is None
        
        # Second item - has total
        assert result[1]["description"] is None
        assert result[1]["total"] == Decimal("100.00")


class TestNormalizeFieldValue:
    """Test individual field value normalization"""
    
    def test_normalize_string_values(self):
        """Test string value normalization"""
        assert _normalize_field_value("  Test String  ", "string", "test") == "Test String"
        assert _normalize_field_value("", "string", "test") is None
        assert _normalize_field_value(None, "string", "test") is None
        assert _normalize_field_value(123, "string", "test") == "123"

    def test_normalize_decimal_values(self):
        """Test decimal value normalization"""
        assert _normalize_field_value("123.45", "decimal", "test") == Decimal("123.45")
        assert _normalize_field_value("$1,234.56", "decimal", "test") == Decimal("1234.56")
        assert _normalize_field_value(100, "decimal", "test") == Decimal("100")
        assert _normalize_field_value(99.99, "decimal", "test") == Decimal("99.99")
        assert _normalize_field_value("invalid", "decimal", "test") is None
        assert _normalize_field_value("", "decimal", "test") is None

    def test_normalize_date_values(self):
        """Test date value normalization"""
        # ISO format
        result = _normalize_field_value("2024-01-15", "date", "test")
        assert result == date(2024, 1, 15)
        
        # US format
        result = _normalize_field_value("01/15/2024", "date", "test")
        assert result == date(2024, 1, 15)
        
        # Datetime object
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = _normalize_field_value(dt, "date", "test")
        assert result == date(2024, 1, 15)
        
        # Date object
        d = date(2024, 1, 15)
        result = _normalize_field_value(d, "date", "test")
        assert result == date(2024, 1, 15)
        
        # Invalid format - return as string
        result = _normalize_field_value("invalid-date", "date", "test")
        assert result == "invalid-date"

    def test_normalize_time_values(self):
        """Test time value normalization"""
        assert _normalize_field_value("14:30:00", "time", "test") == "14:30:00"
        assert _normalize_field_value("  2:30 PM  ", "time", "test") == "2:30 PM"
        assert _normalize_field_value("", "time", "test") is None

    def test_normalize_unknown_type(self):
        """Test normalization with unknown field type"""
        assert _normalize_field_value("test", "unknown_type", "test") == "test"
        assert _normalize_field_value(123, "unknown_type", "test") == "123"


class TestFieldConfidenceSummary:
    """Test confidence summary calculations"""
    
    def test_confidence_summary_complete_fields(self):
        """Test confidence summary with complete field data"""
        normalized_fields = {
            "field1": {"value": "test1", "confidence": 0.9, "raw_value": "test1"},
            "field2": {"value": "test2", "confidence": 0.8, "raw_value": "test2"},
            "field3": {"value": "test3", "confidence": 0.6, "raw_value": "test3"},
            "field4": {"value": None, "confidence": 0.0, "raw_value": ""},
            "field5": {"value": "test5", "confidence": 0.4, "raw_value": "test5"}
        }
        
        result = get_field_confidence_summary(normalized_fields)
        
        assert result["total_fields"] == 5
        assert result["fields_with_values"] == 4
        assert result["fields_without_values"] == 1
        assert result["average_confidence"] == 0.675  # (0.9 + 0.8 + 0.6 + 0.4) / 4
        assert result["high_confidence_fields"] == 2  # >= 0.8
        assert result["medium_confidence_fields"] == 1  # 0.5 <= x < 0.8
        assert result["low_confidence_fields"] == 1  # < 0.5
        assert result["extraction_completeness"] == 0.8  # 4/5

    def test_confidence_summary_empty_fields(self):
        """Test confidence summary with empty fields"""
        result = get_field_confidence_summary({})
        
        assert result["total_fields"] == 0
        assert result["fields_with_values"] == 0
        assert result["average_confidence"] == 0.0
        assert result["extraction_completeness"] == 0.0

    def test_confidence_summary_no_values(self):
        """Test confidence summary with no field values"""
        normalized_fields = {
            "field1": {"value": None, "confidence": 0.0, "raw_value": ""},
            "field2": {"value": None, "confidence": 0.0, "raw_value": ""}
        }
        
        result = get_field_confidence_summary(normalized_fields)
        
        assert result["total_fields"] == 2
        assert result["fields_with_values"] == 0
        assert result["average_confidence"] == 0.0
        assert result["extraction_completeness"] == 0.0


class TestIntegrationScenarios:
    """Test real-world integration scenarios"""
    
    def test_invoice_with_currency_symbols(self):
        """Test invoice normalization with currency symbols and formatting"""
        azure_fields = [
            {"field_name": "vendor_name", "value": "Tech Solutions Inc.", "confidence": 0.96},
            {"field_name": "subtotal", "value": "$2,500.00", "confidence": 0.94},
            {"field_name": "tax_amount", "value": "$200.00", "confidence": 0.92},
            {"field_name": "total_amount", "value": "$2,700.00", "confidence": 0.95}
        ]
        
        result = normalize_invoice_fields(azure_fields)
        
        assert result["subtotal"]["value"] == Decimal("2500.00")
        assert result["tax_amount"]["value"] == Decimal("200.00")
        assert result["total_amount"]["value"] == Decimal("2700.00")

    def test_receipt_with_minimal_data(self):
        """Test receipt normalization with minimal data"""
        azure_fields = [
            {"field_name": "merchant_name", "value": "Quick Mart", "confidence": 0.88},
            {"field_name": "total_amount", "value": "12.34", "confidence": 0.92}
        ]
        
        result = normalize_receipt_fields(azure_fields)
        summary = get_field_confidence_summary(result)
        
        assert result["merchant_name"]["value"] == "Quick Mart"
        assert result["total_amount"]["value"] == Decimal("12.34")
        assert summary["fields_with_values"] == 2
        assert summary["extraction_completeness"] == 0.2  # 2/10 possible fields

    def test_line_items_with_edge_cases(self):
        """Test line item normalization with edge cases"""
        azure_line_items = [
            {
                "description": "  Product with spaces  ",
                "quantity": "2.5",
                "unit_price": "$15.99",
                "total": "$39.98",
                "confidence": 0.93
            },
            {
                "description": "",
                "total": "0.00",
                "confidence": 0.1
            },
            {
                "description": "Valid Item",
                "quantity": "invalid",
                "unit_price": "not-a-number",
                "total": "25.00",
                "confidence": 0.85
            }
        ]
        
        result = normalize_line_items(azure_line_items)
        
        # Should have 3 valid items (all items have at least description or total)
        assert len(result) == 3
        
        # First item - properly cleaned
        assert result[0]["description"] == "Product with spaces"
        assert result[0]["quantity"] == Decimal("2.5")
        assert result[0]["unit_price"] == Decimal("15.99")
        assert result[0]["total"] == Decimal("39.98")
        
        # Second item - empty description but has total
        assert result[1]["description"] is None
        assert result[1]["total"] == Decimal("0.00")
        
        # Third item - invalid numbers handled gracefully
        assert result[2]["description"] == "Valid Item"
        assert result[2]["quantity"] == Decimal("1")  # Default when invalid
        assert result[2]["unit_price"] is None
        assert result[2]["total"] == Decimal("25.00")