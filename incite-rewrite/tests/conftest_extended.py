# Extended fixtures for comprehensive testing

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
        'WTF_CSRF_ENABLED': False,
        'DEBUG': True
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
        },
        'client': client
    }


@pytest.fixture
def sample_texts():
    """
    Provide various sample texts for text processing tests.
    Extended collection with legal and technical content.
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
        'numbers': "Document with numbers: 123, 456.789, $1,000.00, 50% increase.",
        'legal': """
        In Brown v. Board of Education, 347 U.S. 483 (1954), the Supreme Court held that
        state laws establishing separate public schools were unconstitutional. This decision
        overruled Plessy v. Ferguson, 163 U.S. 537 (1896), and cited 42 U.S.C. § 1983
        as providing federal remedies for constitutional violations.
        """,
        'technical': """
        The algorithm implements a recursive descent parser with lookahead capabilities.
        Time complexity is O(n log n) in the average case, with space complexity of O(n).
        Error handling follows the fail-fast principle with comprehensive exception reporting.
        """,
        'empty': "",
        'whitespace_only': "   \n\t   \r\n   ",
        'single_word': "test",
        'single_sentence': "This is a complete sentence."
    }


@pytest.fixture
def data_generator():
    """
    Provide test data generation utilities.
    Creates realistic test data for various scenarios.
    """
    import random
    import string
    from datetime import datetime, timedelta
    
    class DataGenerator:
        @staticmethod
        def random_string(length: int = 10, chars: str = None) -> str:
            if chars is None:
                chars = string.ascii_letters + string.digits
            return ''.join(random.choices(chars, k=length))
        
        @staticmethod
        def random_email(domain: str = None) -> str:
            username = DataGenerator.random_string(8).lower()
            domain = domain or random.choice(['example.com', 'test.org', 'demo.net'])
            return f"{username}@{domain}"
        
        @staticmethod
        def user_data(username: str = None, email: str = None) -> Dict[str, str]:
            return {
                'username': username or DataGenerator.random_string(10).lower(),
                'email': email or DataGenerator.random_email(),
                'password': 'TestPassword123!'
            }
    
    return DataGenerator()


@pytest.fixture
def performance_monitor():
    """
    Provide performance monitoring utilities for tests.
    Measures execution time, memory usage, and other metrics.
    """
    try:
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
    
    except ImportError:
        # Fallback implementation if psutil is not available
        class BasicPerformanceMonitor:
            def __init__(self):
                self.start_time = None
            
            def start(self):
                self.start_time = time.time()
            
            def stop(self):
                if self.start_time is None:
                    raise ValueError("Monitor not started")
                
                return {
                    'duration': time.time() - self.start_time,
                    'memory_delta': 0,  # Not available
                    'memory_peak': 0    # Not available
                }
        
        return BasicPerformanceMonitor()


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