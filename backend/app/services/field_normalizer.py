"""
Field normalization utilities for mapping Azure Document Intelligence output to internal field keys.
Handles missing/null values and provides consistent field mappings for invoices and receipts.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

logger = logging.getLogger(__name__)


def normalize_invoice_fields(azure_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize Azure Document Intelligence invoice fields to internal format.
    
    Maps Azure field names to internal keys and handles missing/null values.
    
    Args:
        azure_fields: List of fields from Azure extraction with structure:
            [{"field_name": str, "value": str, "confidence": float}, ...]
    
    Returns:
        Dictionary with normalized field names and processed values:
        {
            "vendor_name": {"value": str, "confidence": float, "raw_value": str},
            "invoice_date": {"value": date/str, "confidence": float, "raw_value": str},
            "total_amount": {"value": Decimal, "confidence": float, "raw_value": str},
            ...
        }
    """
    if not azure_fields or not isinstance(azure_fields, list):
        logger.warning("Invalid or empty azure_fields provided to normalize_invoice_fields")
        return {}
    
    # Field mapping from Azure Document Intelligence to internal keys
    field_mappings = {
        "vendor_name": {"azure_key": "vendor_name", "type": "string"},
        "vendor_address": {"azure_key": "vendor_address", "type": "string"},
        "customer_name": {"azure_key": "customer_name", "type": "string"},
        "customer_address": {"azure_key": "customer_address", "type": "string"},
        "invoice_number": {"azure_key": "invoice_number", "type": "string"},
        "invoice_date": {"azure_key": "invoice_date", "type": "date"},
        "due_date": {"azure_key": "due_date", "type": "date"},
        "payment_terms": {"azure_key": "payment_terms", "type": "string"},
        "subtotal": {"azure_key": "subtotal", "type": "decimal"},
        "tax_amount": {"azure_key": "tax_amount", "type": "decimal"},
        "total_amount": {"azure_key": "total_amount", "type": "decimal"},
        "amount_due": {"azure_key": "amount_due", "type": "decimal"},
        "purchase_order": {"azure_key": "purchase_order", "type": "string"},
        "billing_address": {"azure_key": "billing_address", "type": "string"},
        "shipping_address": {"azure_key": "shipping_address", "type": "string"}
    }
    
    # Create lookup dict for faster access
    azure_field_lookup = {field["field_name"]: field for field in azure_fields}
    
    normalized_fields = {}
    
    for internal_key, config in field_mappings.items():
        azure_key = config["azure_key"]
        field_type = config["type"]
        
        # Get the field data from Azure results
        field_data = azure_field_lookup.get(azure_key)
        
        if field_data:
            raw_value = field_data.get("value", "")
            confidence = field_data.get("confidence", 0.0)
            
            # Normalize the value based on type
            normalized_value = _normalize_field_value(raw_value, field_type, internal_key)
            
            normalized_fields[internal_key] = {
                "value": normalized_value,
                "confidence": float(confidence),
                "raw_value": str(raw_value) if raw_value is not None else "",
                "field_type": field_type
            }
        else:
            # Handle missing fields
            normalized_fields[internal_key] = {
                "value": None,
                "confidence": 0.0,
                "raw_value": "",
                "field_type": field_type
            }
    
    logger.info(f"Normalized {len([f for f in normalized_fields.values() if f['value'] is not None])}/{len(field_mappings)} invoice fields")
    
    return normalized_fields


def normalize_receipt_fields(azure_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize Azure Document Intelligence receipt fields to internal format.
    
    Maps Azure field names to internal keys and handles missing/null values.
    
    Args:
        azure_fields: List of fields from Azure extraction with structure:
            [{"field_name": str, "value": str, "confidence": float}, ...]
    
    Returns:
        Dictionary with normalized field names and processed values:
        {
            "merchant_name": {"value": str, "confidence": float, "raw_value": str},
            "transaction_date": {"value": date/str, "confidence": float, "raw_value": str},
            "total_amount": {"value": Decimal, "confidence": float, "raw_value": str},
            ...
        }
    """
    if not azure_fields or not isinstance(azure_fields, list):
        logger.warning("Invalid or empty azure_fields provided to normalize_receipt_fields")
        return {}
    
    # Field mapping from Azure Document Intelligence to internal keys
    field_mappings = {
        "merchant_name": {"azure_key": "merchant_name", "type": "string"},
        "merchant_address": {"azure_key": "merchant_address", "type": "string"},
        "merchant_phone": {"azure_key": "merchant_phone", "type": "string"},
        "transaction_date": {"azure_key": "transaction_date", "type": "date"},
        "transaction_time": {"azure_key": "transaction_time", "type": "time"},
        "receipt_type": {"azure_key": "receipt_type", "type": "string"},
        "subtotal": {"azure_key": "subtotal", "type": "decimal"},
        "tax_amount": {"azure_key": "tax_amount", "type": "decimal"},
        "total_amount": {"azure_key": "total_amount", "type": "decimal"},
        "tip_amount": {"azure_key": "tip_amount", "type": "decimal"}
    }
    
    # Create lookup dict for faster access
    azure_field_lookup = {field["field_name"]: field for field in azure_fields}
    
    normalized_fields = {}
    
    for internal_key, config in field_mappings.items():
        azure_key = config["azure_key"]
        field_type = config["type"]
        
        # Get the field data from Azure results
        field_data = azure_field_lookup.get(azure_key)
        
        if field_data:
            raw_value = field_data.get("value", "")
            confidence = field_data.get("confidence", 0.0)
            
            # Normalize the value based on type
            normalized_value = _normalize_field_value(raw_value, field_type, internal_key)
            
            normalized_fields[internal_key] = {
                "value": normalized_value,
                "confidence": float(confidence),
                "raw_value": str(raw_value) if raw_value is not None else "",
                "field_type": field_type
            }
        else:
            # Handle missing fields
            normalized_fields[internal_key] = {
                "value": None,
                "confidence": 0.0,
                "raw_value": "",
                "field_type": field_type
            }
    
    logger.info(f"Normalized {len([f for f in normalized_fields.values() if f['value'] is not None])}/{len(field_mappings)} receipt fields")
    
    return normalized_fields


def normalize_line_items(azure_line_items: List[Dict[str, Any]], document_type: str = "invoice") -> List[Dict[str, Any]]:
    """
    Normalize line items from Azure Document Intelligence to internal format.
    
    Args:
        azure_line_items: List of line items from Azure extraction
        document_type: Type of document ("invoice" or "receipt")
    
    Returns:
        List of normalized line items with consistent structure
    """
    if not azure_line_items or not isinstance(azure_line_items, list):
        return []
    
    normalized_items = []
    
    for idx, item in enumerate(azure_line_items):
        if not isinstance(item, dict):
            continue
        
        # Normalize individual fields
        description = _normalize_field_value(item.get("description", ""), "string", "description")
        quantity = _normalize_field_value(item.get("quantity"), "decimal", "quantity")
        unit_price = _normalize_field_value(item.get("unit_price"), "decimal", "unit_price")
        total = _normalize_field_value(item.get("total"), "decimal", "total")
        
        # Default quantity to 1 if not provided or invalid
        if quantity is None:
            quantity = Decimal("1")
        
        normalized_item = {
            "line_number": idx + 1,
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "total": total,
            "confidence": float(item.get("confidence", 0.0)),
            "raw_data": item
        }
        
        # Ensure we have at least description or total (including zero total)
        if normalized_item["description"] or normalized_item["total"] is not None:
            normalized_items.append(normalized_item)
    
    logger.info(f"Normalized {len(normalized_items)} line items for {document_type}")
    return normalized_items


def _normalize_field_value(
    value: Any, 
    field_type: str, 
    field_name: str
) -> Optional[Union[str, Decimal, datetime, date]]:
    """
    Normalize a single field value based on its expected type.
    
    Args:
        value: Raw value from Azure
        field_type: Expected type (string, decimal, date, time)
        field_name: Field name for logging
    
    Returns:
        Normalized value or None if conversion fails
    """
    if value is None or value == "":
        return None
    
    try:
        if field_type == "string":
            return str(value).strip() if str(value).strip() else None
        
        elif field_type == "decimal":
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            elif isinstance(value, str):
                # Clean up currency symbols and whitespace
                clean_value = value.strip().replace("$", "").replace(",", "").replace(" ", "")
                if clean_value:
                    return Decimal(clean_value)
            return None
        
        elif field_type == "date":
            if isinstance(value, datetime):
                return value.date()
            elif isinstance(value, date):
                return value
            elif isinstance(value, str):
                # Try common date formats
                date_formats = [
                    "%Y-%m-%d",
                    "%m/%d/%Y", 
                    "%d/%m/%Y",
                    "%Y-%m-%d %H:%M:%S",
                    "%m/%d/%Y %H:%M:%S"
                ]
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(value.strip(), fmt)
                        return parsed_date.date()
                    except ValueError:
                        continue
                
                # If no format matches, return the original string
                return value.strip()
            return None
        
        elif field_type == "time":
            return str(value).strip() if str(value).strip() else None
        
        else:
            # Default to string
            return str(value).strip() if str(value).strip() else None
    
    except (ValueError, InvalidOperation, TypeError) as e:
        logger.warning(f"Failed to normalize field {field_name} with value '{value}' as {field_type}: {e}")
        return None


def get_field_confidence_summary(normalized_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate confidence statistics for normalized fields.
    
    Args:
        normalized_fields: Output from normalize_invoice_fields or normalize_receipt_fields
    
    Returns:
        Dictionary with confidence statistics
    """
    if not normalized_fields:
        return {
            "total_fields": 0, 
            "fields_with_values": 0, 
            "fields_without_values": 0,
            "average_confidence": 0.0,
            "high_confidence_fields": 0,
            "medium_confidence_fields": 0,
            "low_confidence_fields": 0,
            "extraction_completeness": 0.0
        }
    
    total_fields = len(normalized_fields)
    fields_with_values = len([f for f in normalized_fields.values() if f["value"] is not None])
    
    confidences = [f["confidence"] for f in normalized_fields.values() if f["value"] is not None]
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Categorize confidence levels
    high_confidence = len([c for c in confidences if c >= 0.8])
    medium_confidence = len([c for c in confidences if 0.5 <= c < 0.8])
    low_confidence = len([c for c in confidences if c < 0.5])
    
    return {
        "total_fields": total_fields,
        "fields_with_values": fields_with_values,
        "fields_without_values": total_fields - fields_with_values,
        "average_confidence": round(average_confidence, 3),
        "high_confidence_fields": high_confidence,
        "medium_confidence_fields": medium_confidence,
        "low_confidence_fields": low_confidence,
        "extraction_completeness": round(fields_with_values / total_fields, 3) if total_fields > 0 else 0.0
    }