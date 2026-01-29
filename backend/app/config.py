"""Application configuration"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "gl2gh Migration Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "change-this-in-production"
    APP_MASTER_KEY: str  # Required for token encryption
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "gl2gh"
    
    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Artifacts Storage
    ARTIFACTS_ROOT: str = "./artifacts"
    
    # API Settings
    API_V1_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # GitLab & GitHub
    GITLAB_BASE_URL: str = "https://gitlab.com"
    GITHUB_API_URL: str = "https://api.github.com"
    
    # Rate Limiting
    MAX_API_CALLS: int = 5000
    MAX_PER_PROJECT_CALLS: int = 200
    
    # Concurrency
    MAX_CONCURRENT_PROJECTS: int = 5
    
    # Microsoft Agent Framework / Azure AI (Optional)
    AZURE_AI_PROJECT_ENDPOINT: Optional[str] = None
    AZURE_AI_MODEL_DEPLOYMENT_NAME: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
