from enum import Enum

class FileType(str, Enum):
    PDF = "PDF"
    JPG = "JPG"
    PNG = "PNG"

class DocumentType(str, Enum):
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"

class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"