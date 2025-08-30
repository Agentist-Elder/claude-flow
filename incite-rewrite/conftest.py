"""
Comprehensive pytest configuration and shared fixtures for London School TDD test suite.
Provides common test utilities, mock objects, and fixtures across all test modules.
Focuses on behavior verification and real system interactions.
"""

import pytest
import os
import tempfile
import shutil
import sqlite3
import time
import json
from typing import Dict, Any, Generator, List, Optional
import logging
from unittest.mock import Mock, patch, MagicMock
import threading
from concurrent.futures import ThreadPoolExecutor

from src.api.endpoints import create_app
from src.auth.authentication import AuthenticationManager
from src.utils.text_processing import TextProcessor
from src.database.connection import DatabaseManager
from src.core.text_analyzer import TextAnalyzer


# Configure test logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Disable verbose logging from dependencies during tests
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)


# ============================================================================
# DATABASE AND FILE SYSTEM FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_database_dir():
    """
    Create temporary directory for test databases.
    Session-scoped to reuse across all tests.
    """
    temp_dir = tempfile.mkdtemp(prefix="incite_test_db_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_db_path(test_database_dir):
    """
    Create temporary database file for individual tests.
    Ensures each test has a clean database state.
    """
    db_fd, db_path = tempfile.mkstemp(suffix='.db', dir=test_database_dir)
    os.close(db_fd)
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def memory_db():
    """
    Provide in-memory database path for tests that don't need persistence.
    Faster for unit tests that don't require file-based database.
    """
    return ":memory:"


# ============================================================================
# AUTHENTICATION AND USER MANAGEMENT FIXTURES  
# ============================================================================

@pytest.fixture
def auth_manager(temp_db_path):
    """
    Create AuthenticationManager instance with temporary database.
    Provides clean authentication state for each test.
    """
    manager = AuthenticationManager(temp_db_path)
    yield manager
    # Cleanup if needed
    if hasattr(manager, 'close'):
        manager.close()


@pytest.fixture
def memory_auth_manager():
    """
    Create AuthenticationManager with in-memory database.
    Faster for tests that don't need persistent authentication data.
    """
    manager = AuthenticationManager(":memory:")
    yield manager
    if hasattr(manager, 'close'):
        manager.close()


@pytest.fixture
def sample_user_data():
    """
    Provide sample user registration data for tests.
    Consistent test data across multiple test files.
    """
    return {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPassword123!'
    }


@pytest.fixture
def registered_user(auth_manager, sample_user_data):
    """
    Register a test user and return user object.
    Provides authenticated user context for tests.
    """
    user = auth_manager.register_user(
        sample_user_data['username'],
        sample_user_data['email'],
        sample_user_data['password']
    )
    return {
        'user': user,
        'password': sample_user_data['password'],
        'auth_manager': auth_manager
    }


# ============================================================================
# TEXT PROCESSING AND ANALYSIS FIXTURES
# ============================================================================

@pytest.fixture
def text_processor(temp_db_path):
    """
    Create TextProcessor instance with temporary database.
    Provides clean text processing state for each test.
    """
    processor = TextProcessor(temp_db_path)
    yield processor
    if hasattr(processor, 'close'):
        processor.close()


@pytest.fixture
def memory_text_processor():
    """
    Create TextProcessor with in-memory database.
    Faster for tests that don't need persistent text data.
    """
    processor = TextProcessor(":memory:")
    yield processor
    if hasattr(processor, 'close'):
        processor.close()


@pytest.fixture
def db_manager(temp_db_path):
    """
    Create DatabaseManager instance with temporary database.
    Provides database connection management for tests.
    """
    manager = DatabaseManager(temp_db_path)
    yield manager
    manager.close_all_connections()


@pytest.fixture
def memory_db_manager():
    """
    Create DatabaseManager with in-memory database.
    Faster for database operation tests.
    """
    manager = DatabaseManager(":memory:")
    yield manager
    manager.close_all_connections()


@pytest.fixture(scope="session")
def test_database_dir():
    """
    Create temporary directory for test databases.
    Session-scoped to reuse across all tests.
    """
    temp_dir = tempfile.mkdtemp(prefix="incite_test_db_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_db_path(test_database_dir):
    """
    Create temporary database file for individual tests.
    Ensures each test has a clean database state.
    """
    db_fd, db_path = tempfile.mkstemp(suffix='.db', dir=test_database_dir)
    os.close(db_fd)
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def memory_db():
    """
    Provide in-memory database path for tests that don't need persistence.
    Faster for unit tests that don't require file-based database.
    """
    return ":memory:"


@pytest.fixture
def auth_manager(temp_db_path):
    """
    Create AuthenticationManager instance with temporary database.
    Provides clean authentication state for each test.
    """
    return AuthenticationManager(temp_db_path)


@pytest.fixture
def memory_auth_manager():
    """
    Create AuthenticationManager with in-memory database.
    Faster for tests that don't need persistent authentication data.
    """
    return AuthenticationManager(":memory:")


@pytest.fixture
def text_processor(temp_db_path):
    """
    Create TextProcessor instance with temporary database.
    Provides clean text processing state for each test.
    """
    return TextProcessor(temp_db_path)


@pytest.fixture
def memory_text_processor():
    """
    Create TextProcessor with in-memory database.
    Faster for tests that don't need persistent text data.
    """
    return TextProcessor(":memory:")


@pytest.fixture
def db_manager(temp_db_path):
    """
    Create DatabaseManager instance with temporary database.
    Provides database connection management for tests.
    """
    return DatabaseManager(temp_db_path)


@pytest.fixture
def memory_db_manager():
    """
    Create DatabaseManager with in-memory database.
    Faster for database operation tests.
    """
    return DatabaseManager(":memory:")


@pytest.fixture
def test_app(temp_db_path):
    """
    Create Flask application instance for testing.
    Configured with test database and settings.
    """
    config = {
        'TESTING': True,
        'DATABASE_PATH': temp_db_path,
        'SECRET_KEY': 'test-secret-key-for-testing-only',
        'WTF_CSRF_ENABLED': False
    }
    
    app = create_app(config)
    
    with app.app_context():
        yield app


@pytest.fixture
def client(test_app):
    """
    Create Flask test client for API endpoint testing.
    Provides HTTP client interface for API tests.
    """
    return test_app.test_client()


@pytest.fixture
def memory_app():
    """
    Create Flask application with in-memory database.
    Faster for API tests that don't need persistent data.
    """
    config = {
        'TESTING': True,
        'DATABASE_PATH': ':memory:',
        'SECRET_KEY': 'memory-test-secret-key'
    }
    
    app = create_app(config)
    
    with app.app_context():
        yield app


@pytest.fixture
def memory_client(memory_app):
    """
    Create Flask test client with in-memory database.
    Faster for API tests without persistence requirements.
    """
    return memory_app.test_client()


@pytest.fixture
def sample_user_data():
    """
    Provide sample user registration data for tests.
    Consistent test data across multiple test files.
    """
    return {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPassword123!'
    }


@pytest.fixture
def registered_user(auth_manager, sample_user_data):
    """
    Register a test user and return user object.
    Provides authenticated user context for tests.
    """
    user = auth_manager.register_user(
        sample_user_data['username'],
        sample_user_data['email'],
        sample_user_data['password']
    )
    return {
        'user': user,
        'password': sample_user_data['password']
    }


@pytest.fixture
def authenticated_user(client, sample_user_data):
    """
    Register user via API and return authentication details.
    Provides complete authentication context including session token.
    """
    # Register user
    response = client.post('/api/auth/register',
                          json=sample_user_data,
                          content_type='application/json')
    
    assert response.status_code == 201
    data = response.get_json()
    
    return {
        'user_data': sample_user_data,
        'user_id': data['user']['user_id'],
        'session_token': data['session_token'],
        'headers': {
            'Authorization': f"Bearer {data['session_token']}",
            'Content-Type': 'application/json'
        }
    }


@pytest.fixture
def sample_texts():
    """
    Provide various sample texts for text processing tests.
    Different text types and sizes for comprehensive testing.
    """
    return {
        'simple': "This is a simple test text.",
        'positive': "This is amazing and wonderful! I love this fantastic experience.",
        'negative': "This is terrible and awful. I hate this horrible experience.",
        'neutral': "This document contains factual information about the system specifications.",
        'complex': """
        Advanced natural language processing techniques enable sophisticated text analysis.
        Machine learning algorithms process linguistic patterns to extract meaningful insights.
        Statistical models evaluate semantic content through computational methods.
        """,
        'long': "This is a longer text document for testing purposes. " * 100,
        'mixed_punctuation': "Hello, world! How are you? I'm fine. Thanks for asking... Great!",
        'special_chars': "Text with special characters: @#$%^&*()_+-={}[]|\\:;\"'<>?,./",
        'unicode': "Text with unicode: café résumé naïve 中文 русский العربية",
        'numbers': "Document with numbers: 123, 456.789, $1,000.00, 50% increase."
    }


@pytest.fixture
def performance_config():
    """
    Provide configuration for performance tests.
    Centralized performance test parameters.
    """
    return {
        'small_iterations': 10,
        'medium_iterations': 50,
        'large_iterations': 100,
        'max_response_time': 1.0,
        'max_memory_usage_mb': 100,
        'min_success_rate': 0.9,
        'concurrent_users': 10,
        'load_test_duration': 30  # seconds
    }


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """
    Automatic cleanup fixture that runs after each test.
    Ensures clean state between tests.
    """
    yield
    
    # Cleanup can be added here if needed
    # For now, individual fixtures handle their own cleanup


# Custom pytest markers
def pytest_configure(config):
    """
    Configure custom pytest markers.
    Allows categorization and selective running of tests.
    """
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow tests (>1s)")
    config.addinivalue_line("markers", "fast: Fast tests (<100ms)")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "text_processing: Text processing tests")
    config.addinivalue_line("markers", "database: Database tests")
    config.addinivalue_line("markers", "api: API endpoint tests")
    config.addinivalue_line("markers", "security: Security tests")


# Test collection customization
def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers automatically.
    Applies markers based on test file paths and names.
    """
    for item in items:
        # Add markers based on file path
        if "test_auth" in item.nodeid:
            item.add_marker(pytest.mark.auth)
        if "test_text_processing" in item.nodeid:
            item.add_marker(pytest.mark.text_processing)
        if "test_api" in item.nodeid:
            item.add_marker(pytest.mark.api)
        if "test_workflows" in item.nodeid:
            item.add_marker(pytest.mark.e2e)
        if "test_benchmarks" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        if "integration/" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "unit/" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        if "e2e/" in item.nodeid:
            item.add_marker(pytest.mark.e2e)
        if "performance/" in item.nodeid:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        # Add slow marker for tests that likely take time
        if any(keyword in item.name.lower() for keyword in ['concurrent', 'load', 'bulk', 'batch', 'performance']):
            item.add_marker(pytest.mark.slow)
        
        # Add fast marker for simple tests
        if any(keyword in item.name.lower() for keyword in ['simple', 'basic', 'unit']) and 'integration' not in item.nodeid:
            item.add_marker(pytest.mark.fast)


# Performance test utilities
@pytest.fixture
def performance_monitor():
    """
    Provide performance monitoring utilities for tests.
    Measures execution time, memory usage, and other metrics.
    """
    import psutil
    
    class PerformanceMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.start_time = None
            self.start_memory = None
        
        def start(self):
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        def stop(self):
            if self.start_time is None:
                raise ValueError("Monitor not started")
            
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            
            return {
                'duration': end_time - self.start_time,
                'memory_delta': end_memory - self.start_memory,
                'memory_peak': end_memory
            }
    
    return PerformanceMonitor()


# Database verification utilities
@pytest.fixture
def db_validator():
    """
    Provide database validation utilities for tests.
    Helps verify database state and integrity.
    """
    class DatabaseValidator:
        def __init__(self, db_path):
            self.db_path = db_path
        
        def table_exists(self, table_name: str) -> bool:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return cursor.fetchone() is not None
        
        def count_rows(self, table_name: str) -> int:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cursor.fetchone()[0]
        
        def get_row(self, table_name: str, **conditions) -> Dict[str, Any]:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                where_clause = " AND ".join([f"{key} = ?" for key in conditions.keys()])
                values = list(conditions.values())
                
                cursor = conn.execute(f"SELECT * FROM {table_name} WHERE {where_clause}", values)
                row = cursor.fetchone()
                
                return dict(row) if row else None
    
    return lambda db_path: DatabaseValidator(db_path)


# Test data generators
@pytest.fixture
def data_generator():
    """
    Provide test data generation utilities.
    Creates realistic test data for various scenarios.
    """
    import random
    import string
    
    class DataGenerator:
        @staticmethod
        def random_string(length: int = 10) -> str:
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        
        @staticmethod
        def random_email() -> str:
            username = DataGenerator.random_string(8).lower()
            domain = random.choice(['example.com', 'test.org', 'demo.net'])
            return f"{username}@{domain}"
        
        @staticmethod
        def random_text(word_count: int = 50) -> str:
            words = ['the', 'quick', 'brown', 'fox', 'jumps', 'over', 'lazy', 'dog',
                    'lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur', 'adipiscing',
                    'elit', 'sed', 'do', 'eiusmod', 'tempor', 'incididunt', 'ut', 'labore']
            
            return ' '.join(random.choices(words, k=word_count)) + '.'
        
        @staticmethod
        def user_data(username: str = None) -> Dict[str, str]:
            return {
                'username': username or DataGenerator.random_string(10).lower(),
                'email': DataGenerator.random_email(),
                'password': 'TestPassword123!'
            }
    
    return DataGenerator()


# Test environment info
def pytest_report_header(config):
    """
    Add custom header information to pytest report.
    Shows test environment details.
    """
    return [
        "Incite Rewrite Test Suite - London School TDD Methodology",
        "Testing real behavior and interactions without mocks",
        "Focus on behavior verification and actual system validation",
        f"Python version: {os.sys.version}",
        f"Test database directory: {tempfile.gettempdir()}/incite_test_*"
    ]