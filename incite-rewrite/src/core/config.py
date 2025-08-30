from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import secrets
import os


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "InciteRewrite API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    
    # Security settings
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    
    # Database settings
    DATABASE_URL: str = Field(env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=30, env="DATABASE_MAX_OVERFLOW")
    
    # Redis settings
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    REDIS_TTL: int = Field(default=3600, env="REDIS_TTL")
    
    # Rate limiting settings
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=3600, env="RATE_LIMIT_WINDOW")  # 1 hour
    
    # CORS settings
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    CORS_METHODS: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    CORS_HEADERS: List[str] = Field(default=["*"])
    
    # WebSocket settings
    WEBSOCKET_ENABLED: bool = Field(default=True, env="WEBSOCKET_ENABLED")
    WEBSOCKET_PING_INTERVAL: int = Field(default=25, env="WEBSOCKET_PING_INTERVAL")
    WEBSOCKET_PING_TIMEOUT: int = Field(default=20, env="WEBSOCKET_PING_TIMEOUT")
    
    # Monitoring settings
    PROMETHEUS_ENABLED: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    PROMETHEUS_PORT: int = Field(default=8000, env="PROMETHEUS_PORT")
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # AI/Text Processing settings
    AI_SERVICE_URL: Optional[str] = Field(default=None, env="AI_SERVICE_URL")
    AI_SERVICE_API_KEY: Optional[str] = Field(default=None, env="AI_SERVICE_API_KEY")
    MAX_TEXT_LENGTH: int = Field(default=50000, env="MAX_TEXT_LENGTH")
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Configuration for different environments
class DevelopmentConfig(Settings):
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10


class TestingConfig(Settings):
    DEBUG: bool = True
    ENVIRONMENT: str = "testing"
    LOG_LEVEL: str = "DEBUG"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    RATE_LIMIT_REQUESTS: int = 1000  # Higher limit for testing


class ProductionConfig(Settings):
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"


def get_settings() -> Settings:
    """Factory function to get settings based on environment."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return ProductionConfig()