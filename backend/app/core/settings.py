from pydantic_settings import BaseSettings
from typing import Optional


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
    
    # OpenAI settings
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-3-small"

    # Application settings
    debug: bool = False
    environment: str = "development"
    
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