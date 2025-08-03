"""
Azure Form Recognizer (Document Intelligence) client for extracting structured data from documents.
Implements prebuilt invoice and receipt models for financial document processing.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from ..core.settings import get_settings
from ..enums import DocumentType
from .blob import get_azure_blob_service

logger = logging.getLogger(__name__)


class DocumentExtractionError(Exception):
    """Custom exception for document extraction errors"""
    pass


class AzureFormRecognizerClient:
    """
    Azure Document Intelligence client for extracting structured data from documents.
    
    Supports prebuilt models for:
    - Invoices: Extracts vendor, dates, amounts, line items, etc.
    - Receipts: Extracts merchant, date, amounts, line items, etc.
    """
    
    def __init__(self):
        """Initialize the Azure Document Intelligence client"""
        self.settings = get_settings()
        
        # Initialize the client with primary key
        self.client = DocumentIntelligenceClient(
            endpoint=self.settings.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(self.settings.azure_document_intelligence_key_one)
        )
        
        # Prebuilt model IDs
        self.INVOICE_MODEL = "prebuilt-invoice"
        self.RECEIPT_MODEL = "prebuilt-receipt"
    
    async def extract_fields(
        self, 
        file_url: str, 
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Extract structured fields from a document using Azure Document Intelligence.
        
        Args:
            file_url: URL of the document to analyze (must be publicly accessible)
            document_type: Type of document (INVOICE or RECEIPT)
            
        Returns:
            Dictionary containing extracted fields and line items with confidence scores
            
        Raises:
            DocumentExtractionError: If extraction fails or unsupported document type
        """
        if not file_url:
            raise DocumentExtractionError("File URL is required")
        
        # Select the appropriate prebuilt model
        model_id = self._get_model_id(document_type)
        
        try:
            logger.info(f"Starting document analysis for {file_url} using model {model_id}")
            
            # Generate SAS URL for Azure Document Intelligence to access the blob
            blob_service = get_azure_blob_service()
            sas_url = blob_service.generate_sas_url(file_url, expiry_hours=2)
            logger.info(f"Generated SAS URL for Document Intelligence access")
            
            # Create the analysis request with SAS URL
            analyze_request = AnalyzeDocumentRequest(url_source=sas_url)
            
            # Start the analysis operation
            poller = self.client.begin_analyze_document(
                model_id=model_id,
                body=analyze_request
            )
            
            # Wait for completion and get results
            result: AnalyzeResult = poller.result()
            
            # Extract structured data based on document type
            if document_type == DocumentType.INVOICE:
                extracted_data = self._extract_invoice_fields(result)
            elif document_type == DocumentType.RECEIPT:
                extracted_data = self._extract_receipt_fields(result)
            else:
                raise DocumentExtractionError(f"Unsupported document type: {document_type}")
            
            logger.info(f"Successfully extracted {len(extracted_data.get('fields', []))} fields and {len(extracted_data.get('line_items', []))} line items")
            
            return extracted_data
            
        except HttpResponseError as e:
            error_msg = f"Azure API error during document analysis: {e}"
            logger.error(error_msg)
            raise DocumentExtractionError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Unexpected error during document analysis: {e}"
            logger.error(error_msg)
            raise DocumentExtractionError(error_msg) from e
    
    def _get_model_id(self, document_type: DocumentType) -> str:
        """Get the appropriate Azure prebuilt model ID for the document type"""
        if document_type == DocumentType.INVOICE:
            return self.INVOICE_MODEL
        elif document_type == DocumentType.RECEIPT:
            return self.RECEIPT_MODEL
        else:
            raise DocumentExtractionError(f"No Azure model available for document type: {document_type}")
    
    def _extract_invoice_fields(self, result: AnalyzeResult) -> Dict[str, Any]:
        """
        Extract invoice fields from Azure Document Intelligence results.
        
        Returns dictionary with 'fields' and 'line_items' keys.
        """
        extracted_fields = []
        line_items = []
        
        if not result.documents:
            logger.warning("No documents found in analysis result")
            return {"fields": extracted_fields, "line_items": line_items}
        
        # Process the first document (assuming single document analysis)
        document = result.documents[0]
        fields = document.fields or {}
        
        # Extract key invoice fields
        field_mappings = {
            "VendorName": "vendor_name",
            "VendorAddress": "vendor_address",
            "CustomerName": "customer_name",
            "CustomerAddress": "customer_address",
            "InvoiceId": "invoice_number",
            "InvoiceDate": "invoice_date",
            "DueDate": "due_date",
            "PaymentTerms": "payment_terms",
            "SubTotal": "subtotal",
            "TotalTax": "tax_amount",
            "InvoiceTotal": "total_amount",
            "AmountDue": "amount_due",
            "PurchaseOrder": "purchase_order",
            "BillingAddress": "billing_address",
            "ShippingAddress": "shipping_address"
        }
        
        for azure_field, our_field in field_mappings.items():
            if azure_field in fields:
                field_data = fields[azure_field]
                value = self._extract_field_value(field_data)
                confidence = getattr(field_data, 'confidence', 0.0) if field_data else 0.0
                
                if value is not None:
                    extracted_fields.append({
                        "field_name": our_field,
                        "value": str(value),
                        "confidence": confidence
                    })
        
        # Extract line items
        if "Items" in fields and fields["Items"]:
            items_field = fields["Items"]
            if hasattr(items_field, 'value_array') and items_field.value_array:
                for item in items_field.value_array:
                    line_item = self._extract_invoice_line_item(item)
                    if line_item:
                        line_items.append(line_item)
        
        return {
            "fields": extracted_fields,
            "line_items": line_items
        }
    
    def _extract_receipt_fields(self, result: AnalyzeResult) -> Dict[str, Any]:
        """
        Extract receipt fields from Azure Document Intelligence results.
        
        Returns dictionary with 'fields' and 'line_items' keys.
        """
        extracted_fields = []
        line_items = []
        
        if not result.documents:
            logger.warning("No documents found in analysis result")
            return {"fields": extracted_fields, "line_items": line_items}
        
        # Process the first document
        document = result.documents[0]
        fields = document.fields or {}
        
        # Extract key receipt fields
        field_mappings = {
            "MerchantName": "merchant_name",
            "MerchantAddress": "merchant_address",
            "MerchantPhoneNumber": "merchant_phone",
            "TransactionDate": "transaction_date",
            "TransactionTime": "transaction_time",
            "ReceiptType": "receipt_type",
            "Subtotal": "subtotal",
            "Tax": "tax_amount",
            "Total": "total_amount",
            "Tip": "tip_amount"
        }
        
        for azure_field, our_field in field_mappings.items():
            if azure_field in fields:
                field_data = fields[azure_field]
                value = self._extract_field_value(field_data)
                confidence = getattr(field_data, 'confidence', 0.0) if field_data else 0.0
                
                if value is not None:
                    extracted_fields.append({
                        "field_name": our_field,
                        "value": str(value),
                        "confidence": confidence
                    })
        
        # Extract line items
        if "Items" in fields and fields["Items"]:
            items_field = fields["Items"]
            if hasattr(items_field, 'value_array') and items_field.value_array:
                for item in items_field.value_array:
                    line_item = self._extract_receipt_line_item(item)
                    if line_item:
                        line_items.append(line_item)
        
        return {
            "fields": extracted_fields,
            "line_items": line_items
        }
    
    def _extract_invoice_line_item(self, item_field) -> Optional[Dict[str, Any]]:
        """Extract a single invoice line item from Azure field data"""
        if not item_field or not hasattr(item_field, 'value_object'):
            return None
        
        item_data = item_field.value_object
        if not item_data:
            return None
        
        line_item = {}
        
        # Extract description
        if "Description" in item_data and item_data["Description"]:
            line_item["description"] = self._extract_field_value(item_data["Description"])
        
        # Extract quantity
        if "Quantity" in item_data and item_data["Quantity"]:
            qty_value = self._extract_field_value(item_data["Quantity"])
            if qty_value is not None:
                try:
                    line_item["quantity"] = Decimal(str(qty_value))
                except (ValueError, TypeError, Exception):
                    line_item["quantity"] = Decimal("1.0")
        
        # Extract unit price
        if "UnitPrice" in item_data and item_data["UnitPrice"]:
            price_value = self._extract_field_value(item_data["UnitPrice"])
            if price_value is not None:
                try:
                    line_item["unit_price"] = Decimal(str(price_value))
                except (ValueError, TypeError, Exception):
                    pass
        
        # Extract total amount
        if "Amount" in item_data and item_data["Amount"]:
            amount_value = self._extract_field_value(item_data["Amount"])
            if amount_value is not None:
                try:
                    line_item["total"] = Decimal(str(amount_value))
                except (ValueError, TypeError, Exception):
                    pass
        
        # Calculate confidence (average of available field confidences)
        confidences = []
        for field_name in ["Description", "Quantity", "UnitPrice", "Amount"]:
            if field_name in item_data and item_data[field_name]:
                conf = getattr(item_data[field_name], 'confidence', 0.0)
                if conf > 0:
                    confidences.append(conf)
        
        line_item["confidence"] = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Only return if we have at least a description or amount
        if line_item.get("description") or line_item.get("total"):
            return line_item
        
        return None
    
    def _extract_receipt_line_item(self, item_field) -> Optional[Dict[str, Any]]:
        """Extract a single receipt line item from Azure field data"""
        if not item_field or not hasattr(item_field, 'value_object'):
            return None
        
        item_data = item_field.value_object
        if not item_data:
            return None
        
        line_item = {}
        
        # Extract description (Name field in receipts)
        if "Name" in item_data and item_data["Name"]:
            line_item["description"] = self._extract_field_value(item_data["Name"])
        
        # Extract quantity
        if "Quantity" in item_data and item_data["Quantity"]:
            qty_value = self._extract_field_value(item_data["Quantity"])
            if qty_value is not None:
                try:
                    line_item["quantity"] = Decimal(str(qty_value))
                except (ValueError, TypeError, Exception):
                    line_item["quantity"] = Decimal("1.0")
        else:
            # Default to 1 for receipts if not specified
            line_item["quantity"] = Decimal("1.0")
        
        # Extract price (usually the total price for receipt items)
        if "Price" in item_data and item_data["Price"]:
            price_value = self._extract_field_value(item_data["Price"])
            if price_value is not None:
                try:
                    price_decimal = Decimal(str(price_value))
                    line_item["total"] = price_decimal
                    # Calculate unit price if we have quantity
                    if line_item.get("quantity", 0) > 0:
                        line_item["unit_price"] = price_decimal / line_item["quantity"]
                except (ValueError, TypeError, Exception):
                    pass
        
        # Calculate confidence
        confidences = []
        for field_name in ["Name", "Quantity", "Price"]:
            if field_name in item_data and item_data[field_name]:
                conf = getattr(item_data[field_name], 'confidence', 0.0)
                if conf > 0:
                    confidences.append(conf)
        
        line_item["confidence"] = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Only return if we have at least a description or total
        if line_item.get("description") or line_item.get("total"):
            return line_item
        
        return None
    
    def _extract_field_value(self, field_data) -> Optional[Union[str, float, int]]:
        """Extract the actual value from an Azure field data object"""
        if not field_data:
            return None
        
        # Try different value attributes that Azure uses
        for attr in ['value_string', 'value_number', 'value_date', 'value_time', 'value_phone_number', 'content']:
            if hasattr(field_data, attr):
                value = getattr(field_data, attr)
                if value is not None:
                    return value
        
        # If it's a Mock object for testing, try getting the expected attribute
        if hasattr(field_data, 'value'):
            return field_data.value
            
        return None


def get_azure_form_recognizer_client() -> AzureFormRecognizerClient:
    """Get a configured Azure Form Recognizer client instance"""
    return AzureFormRecognizerClient()