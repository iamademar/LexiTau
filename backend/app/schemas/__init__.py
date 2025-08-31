# Auth schemas
from .auth import (
    SignupRequest,
    LoginRequest,
    Token,
    UserResponse,
    BusinessResponse,
    SignupResponse,
    LoginResponse
)

# Document schemas
from .document import (
    DocumentUploadResult,
    DocumentUploadResponse,
    DocumentBase,
    DocumentCreate,
    DocumentResponse,
    DocumentFilters,
    PaginationMeta,
    DocumentListResponse,
    ExtractedFieldResponse,
    LineItemResponse,
    DocumentFieldsResponse,
    FieldCorrectionRequest,
    FieldCorrectionsRequest,
    FieldCorrectionResult,
    FieldCorrectionsResponse,
    LineItemUpdateRequest,
    LineItemUpdateResponse,
    MarkReviewedRequest,
    MarkReviewedResponse,
    DocumentTagRequest,
    DocumentTagResponse
)

# User schemas
from .user import UserBase

# Item schemas  
from .item import ItemBase

# Client schemas
from .client import (
    ClientBase,
    ClientCreate,
    Client
)

# Project schemas
from .project import (
    ProjectBase,
    ProjectCreate,
    Project
)

# Category schemas
from .category import (
    CategoryBase,
    Category
)

# Make all schemas available at package level
__all__ = [
    # Auth
    "SignupRequest",
    "LoginRequest", 
    "Token",
    "UserResponse",
    "BusinessResponse",
    "SignupResponse",
    "LoginResponse",
    # Document
    "DocumentUploadResult",
    "DocumentUploadResponse",
    "DocumentBase",
    "DocumentCreate", 
    "DocumentResponse",
    "DocumentFilters",
    "PaginationMeta",
    "DocumentListResponse",
    "ExtractedFieldResponse",
    "LineItemResponse",
    "DocumentFieldsResponse",
    "FieldCorrectionRequest",
    "FieldCorrectionsRequest",
    "FieldCorrectionResult",
    "FieldCorrectionsResponse",
    "LineItemUpdateRequest",
    "LineItemUpdateResponse",
    "MarkReviewedRequest",
    "MarkReviewedResponse",
    "DocumentTagRequest",
    "DocumentTagResponse",
    # User
    "UserBase",
    # Item
    "ItemBase",
    # Client
    "ClientBase",
    "ClientCreate",
    "Client",
    # Project
    "ProjectBase",
    "ProjectCreate",
    "Project",
    # Category
    "CategoryBase",
    "Category"
]