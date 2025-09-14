from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database settings
    database_url: str = "postgresql://postgres:password@localhost:5432/lexitau"
    test_database_url: str = "postgresql://postgres:password@localhost:5435/lexitau_test"
    
    # JWT settings
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Azure Blob Storage settings
    azure_storage_account_name: str
    azure_storage_account_key: Optional[str] = None
    azure_storage_connection_string: Optional[str] = None
    azure_blob_container_name: str = "documents"
    
    # Redis/Celery settings
    redis_url: str = "redis://localhost:6379/0"
    
    # Azure Document Intelligence settings
    azure_document_intelligence_key_one: str
    azure_document_intelligence_key_two: Optional[str] = None
    azure_document_intelligence_region: str
    azure_document_intelligence_endpoint: str
    
    # Application settings
    debug: bool = False
    environment: str = "development"

    # Vanna AI settings
    # Required
    vanna_model: str = ""
    vanna_api_key: str = ""

    # Allow-list
    vanna_allowed_schemas: List[str] = ["public"]
    vanna_allowed_tables: List[str] = [
        "public.documents", "public.line_items", "public.extracted_fields",
        "public.clients", "public.projects", "public.categories",
    ]

    # Tenant scope symmetry
    vanna_tenant_column: str = "business_id"
    vanna_tenant_param: str = "business_id"

    # Defaults
    vanna_default_timeout_s: int = 5
    vanna_default_row_limit: int = 500
    vanna_work_mem: Optional[str] = None

    # SELECT * expansion
    vanna_expand_select_star: bool = True
    vanna_expand_exclude_types: List[str] = ["bytea"]
    vanna_expand_exclude_name_patterns: List[str] = ["password", "secret", "api[_-]?key", "token"]

    # Per-table excludes (affect SELECT * only; explicit selects still allowed)
    vanna_expand_exclude_columns: List[str] = [
        "public.users.password_hash",
        "public.documents.file_url",
        "public.users.email",
        "public.extracted_fields.value",
        "public.field_corrections.original_value",
        "public.field_corrections.corrected_value",
        "public.line_items.description",
    ]

    # Tenant per alias (all allowed tables are required)
    vanna_tenant_enforce_per_table: bool = True
    vanna_tenant_required_tables: List[str] = [
        "public.documents", "public.line_items", "public.extracted_fields",
        "public.clients", "public.projects", "public.categories",
    ]

    # Function deny-list (case-insensitive regex)
    vanna_function_denylist: List[str] = [
        r"^pg_sleep(?:_for|_until)?$",
        r"^dblink.*$",
        r"^pg_(?:read|read_binary|write|stat)_file$",
        r"^pg_ls_dir$",
        r"^pg_logdir_ls$",
        r"^lo_.*$",
        r"^pg_terminate_backend$",
        r"^pg_cancel_backend$",
        r"^pg_reload_conf$",
        r"^pg_rotate_logfile$",
        r"^set_config$",
        r"^pg_advisory_(?:xact_)?lock$",
        r"^pg_try_advisory_(?:xact_)?lock$",
        r"^pg_promote$",
        r"^pg_checkpoint$",
        r"^pg_stat_reset.*$",
    ]

    # Auditing & error mapping
    vanna_audit_enabled: bool = True
    vanna_audit_redact: bool = False
    vanna_always_200_on_errors: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def azure_connection_string(self) -> str:
        """Get Azure connection string from explicit connection string or build from account details"""
        if self.azure_storage_connection_string:
            return self.azure_storage_connection_string
        
        if self.azure_storage_account_key:
            return f"DefaultEndpointsProtocol=https;AccountName={self.azure_storage_account_name};AccountKey={self.azure_storage_account_key};EndpointSuffix=core.windows.net"
        
        raise ValueError("Either azure_storage_connection_string or azure_storage_account_key must be provided")


# Global settings instance
def get_settings() -> Settings:
    """Get application settings instance"""
    return Settings()