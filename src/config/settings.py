"""
Configuration settings for InciteRewrite application.
Privacy-first design with secure defaults.
"""
import os
from datetime import timedelta

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # Database configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or 'inciterewrite.db'
    
    # Session configuration
    SESSION_TIMEOUT = timedelta(hours=1)
    PERMANENT_SESSION_LIFETIME = SESSION_TIMEOUT
    
    # CourtListener API configuration
    COURTLISTENER_API_URL = "https://www.courtlistener.com/api/rest/v3/"
    COURTLISTENER_API_KEY = os.environ.get('COURTLISTENER_API_KEY')
    COURTLISTENER_RATE_LIMIT = 100  # requests per hour
    
    # Security settings
    DOCUMENT_RETENTION_POLICY = "NO_STORAGE"  # Never store document content
    HASH_ALGORITHM = "SHA256"
    
    # Performance settings
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
    CITATION_PROCESSING_TIMEOUT = 30  # seconds
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = ':memory:'
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': DevelopmentConfig
}