"""
Comprehensive Flask application tests using London School TDD approach.
Tests validate HTTP behavior, middleware interactions, and endpoint responses.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from src.api.endpoints import create_app, APIError, benchmark_endpoint
from src.auth.authentication import AuthenticationError


class TestFlaskAppCreation:
    """Test Flask application creation and configuration."""
    
    def test_creates_app_with_default_config(self):
        """Should create Flask app with default configuration."""
        app = create_app()
        
        assert isinstance(app, Flask)
        assert app.config['SECRET_KEY'] == 'dev-secret-key-change-in-production'
        assert app.config['DATABASE_PATH'] == ':memory:'
        assert not app.config['TESTING']
    
    def test_creates_app_with_test_config(self):
        """Should create Flask app with provided test configuration."""
        test_config = {
            'TESTING': True,
            'SECRET_KEY': 'test-secret',
            'DATABASE_PATH': '/tmp/test.db'
        }
        
        app = create_app(test_config)
        
        assert app.config['TESTING']
        assert app.config['SECRET_KEY'] == 'test-secret'
        assert app.config['DATABASE_PATH'] == '/tmp/test.db'
    
    def test_registers_cors_middleware(self, test_app):
        """Should register CORS middleware for cross-origin requests."""
        with test_app.test_client() as client:
            response = client.options('/api/auth/register')
            
            # CORS headers should be present
            assert 'Access-Control-Allow-Origin' in response.headers


class TestAuthenticationMiddleware:
    """Test authentication middleware behavior."""
    
    def test_require_auth_validates_bearer_token(self, client, authenticated_user):
        """Should validate Bearer token in Authorization header."""
        # Test with valid token
        response = client.get('/api/auth/profile', 
                            headers=authenticated_user['headers'])
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['user']['user_id'] == authenticated_user['user_id']
    
    def test_require_auth_rejects_missing_header(self, client):
        """Should reject requests without Authorization header."""
        response = client.get('/api/auth/profile')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Missing or invalid authorization header' in data['error']
    
    def test_require_auth_rejects_invalid_token_format(self, client):
        """Should reject Authorization headers without Bearer prefix."""
        headers = {'Authorization': 'InvalidToken123'}
        response = client.get('/api/auth/profile', headers=headers)
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Missing or invalid authorization header' in data['error']
    
    def test_require_auth_rejects_expired_token(self, client, sample_user_data):
        """Should reject expired or invalid session tokens."""
        headers = {'Authorization': 'Bearer expired_or_invalid_token'}
        response = client.get('/api/auth/profile', headers=headers)
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid or expired session' in data['error']


class TestErrorHandling:
    """Test application error handling behavior."""
    
    def test_handles_api_error_with_custom_status_code(self, test_app):
        """Should handle APIError with custom status code."""
        @test_app.route('/test_api_error')
        def test_route():
            raise APIError('Custom error message', 400)
        
        with test_app.test_client() as client:
            response = client.get('/test_api_error')
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['error'] == 'Custom error message'
    
    def test_handles_authentication_error(self, test_app):
        """Should handle AuthenticationError with 401 status."""
        @test_app.route('/test_auth_error')
        def test_route():
            raise AuthenticationError('Authentication failed')
        
        with test_app.test_client() as client:
            response = client.get('/test_auth_error')
            
            assert response.status_code == 401
            data = response.get_json()
            assert 'Authentication failed' in data['error']
    
    def test_handles_value_error(self, test_app):
        """Should handle ValueError with 400 status."""
        @test_app.route('/test_value_error')
        def test_route():
            raise ValueError('Invalid value provided')
        
        with test_app.test_client() as client:
            response = client.get('/test_value_error')
            
            assert response.status_code == 400
            data = response.get_json()
            assert 'Invalid value provided' in data['error']
    
    def test_handles_general_exception(self, test_app):
        """Should handle unexpected exceptions with 500 status."""
        @test_app.route('/test_general_error')
        def test_route():
            raise RuntimeError('Unexpected error')
        
        with test_app.test_client() as client:
            response = client.get('/test_general_error')
            
            assert response.status_code == 500
            data = response.get_json()
            assert data['error'] == 'Internal server error'


class TestMiddlewareBehavior:
    """Test middleware interaction and behavior."""
    
    def test_adds_security_headers(self, client):
        """Should add security headers to all responses."""
        response = client.get('/health')
        
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('X-Frame-Options') == 'DENY'
        assert response.headers.get('X-XSS-Protection') == '1; mode=block'
        assert 'Content-Security-Policy' in response.headers
        assert 'Referrer-Policy' in response.headers
    
    def test_adds_process_time_header(self, client):
        """Should add process time header to responses."""
        response = client.get('/health')
        
        assert 'X-Process-Time' in response.headers
        process_time = float(response.headers['X-Process-Time'].rstrip('s'))
        assert process_time >= 0
    
    def test_logs_api_usage(self, client, caplog):
        """Should log API usage with method, path, and timing."""
        with caplog.at_level('INFO'):
            response = client.get('/health')
            
        assert response.status_code == 200
        
        # Check that API usage was logged
        log_messages = [record.message for record in caplog.records]
        api_log_found = any('GET /health - 200' in msg for msg in log_messages)
        assert api_log_found


class TestHealthCheckEndpoints:
    """Test health check endpoint behavior."""
    
    def test_health_endpoint_returns_status(self, client):
        """Should return healthy status with version info."""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert data['version'] == '1.0.0'
    
    @patch('sqlite3.connect')
    def test_health_endpoint_handles_db_error(self, mock_connect, client):
        """Should return unhealthy status when database fails."""
        mock_connect.side_effect = Exception('Database connection failed')
        
        response = client.get('/health')
        
        assert response.status_code == 503
        data = response.get_json()
        assert data['status'] == 'unhealthy'
        assert 'Database connection failed' in data['error']
        assert 'timestamp' in data


class TestUserRegistrationEndpoint:
    """Test user registration endpoint behavior and interactions."""
    
    def test_registers_user_successfully(self, client, sample_user_data):
        """Should register new user and return user data with session token."""
        response = client.post('/api/auth/register',
                              json=sample_user_data,
                              content_type='application/json')
        
        assert response.status_code == 201
        data = response.get_json()
        
        assert data['success'] is True
        assert data['user']['username'] == sample_user_data['username']
        assert data['user']['email'] == sample_user_data['email']
        assert 'user_id' in data['user']
        assert 'session_token' in data
        assert 'created_at' in data['user']
    
    def test_rejects_missing_json_data(self, client):
        """Should reject requests without JSON data."""
        response = client.post('/api/auth/register')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'JSON data required'
    
    def test_validates_required_fields(self, client):
        """Should validate presence of username, email, and password."""
        incomplete_data = {'username': 'test'}
        response = client.post('/api/auth/register',
                              json=incomplete_data,
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Username, email, and password are required' in data['error']
    
    def test_handles_duplicate_user_registration(self, client, sample_user_data):
        """Should handle duplicate user registration gracefully."""
        # First registration should succeed
        response1 = client.post('/api/auth/register',
                               json=sample_user_data,
                               content_type='application/json')
        assert response1.status_code == 201
        
        # Second registration should fail
        response2 = client.post('/api/auth/register',
                               json=sample_user_data,
                               content_type='application/json')
        assert response2.status_code == 400
        data = response2.get_json()
        assert 'error' in data


class TestUserLoginEndpoint:
    """Test user login endpoint behavior and session creation."""
    
    def test_authenticates_valid_credentials(self, client, sample_user_data):
        """Should authenticate user with valid credentials and create session."""
        # Register user first
        client.post('/api/auth/register',
                   json=sample_user_data,
                   content_type='application/json')
        
        # Login with credentials
        login_data = {
            'username': sample_user_data['username'],
            'password': sample_user_data['password']
        }
        response = client.post('/api/auth/login',
                              json=login_data,
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert data['user']['username'] == sample_user_data['username']
        assert 'session_token' in data
        assert 'last_login' in data['user']
    
    def test_rejects_invalid_credentials(self, client, sample_user_data):
        """Should reject authentication with invalid credentials."""
        login_data = {
            'username': 'nonexistent_user',
            'password': 'wrong_password'
        }
        response = client.post('/api/auth/login',
                              json=login_data,
                              content_type='application/json')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid credentials' in data['error']
    
    def test_validates_login_fields(self, client):
        """Should validate presence of username and password fields."""
        incomplete_data = {'username': 'test'}
        response = client.post('/api/auth/login',
                              json=incomplete_data,
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Username and password are required' in data['error']


class TestTextAnalysisEndpoint:
    """Test text analysis endpoint behavior and processing integration."""
    
    def test_analyzes_text_successfully(self, client, authenticated_user, sample_texts):
        """Should analyze text and return comprehensive analysis results."""
        text_data = {
            'text': sample_texts['complex'],
            'store_result': True
        }
        
        response = client.post('/api/text/analyze',
                              json=text_data,
                              headers=authenticated_user['headers'])
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        analysis = data['analysis']
        
        # Verify analysis contains expected metrics
        assert 'word_count' in analysis
        assert 'character_count' in analysis
        assert 'sentence_count' in analysis
        assert 'paragraph_count' in analysis
        assert 'readability_score' in analysis
        assert 'sentiment_score' in analysis
        assert 'common_words' in analysis
        assert 'processing_time' in analysis
        
        # Verify metrics are reasonable
        assert analysis['word_count'] > 0
        assert analysis['character_count'] > analysis['word_count']
        assert analysis['processing_time'] > 0
    
    def test_requires_authentication(self, client, sample_texts):
        """Should require authentication to access text analysis."""
        text_data = {'text': sample_texts['simple']}
        response = client.post('/api/text/analyze', json=text_data)
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Missing or invalid authorization header' in data['error']
    
    def test_validates_text_content(self, client, authenticated_user):
        """Should validate that text content is provided."""
        text_data = {'text': ''}
        response = client.post('/api/text/analyze',
                              json=text_data,
                              headers=authenticated_user['headers'])
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Text content is required' in data['error']
    
    def test_rejects_oversized_text(self, client, authenticated_user):
        """Should reject text content exceeding size limits."""
        large_text = 'A' * 100001  # Exceed 100KB limit
        text_data = {'text': large_text}
        
        response = client.post('/api/text/analyze',
                              json=text_data,
                              headers=authenticated_user['headers'])
        
        assert response.status_code == 413
        data = response.get_json()
        assert 'Text content too large' in data['error']


class TestTextSearchEndpoint:
    """Test text search endpoint behavior and database interaction."""
    
    def test_searches_documents_by_word(self, client, authenticated_user, text_processor, sample_texts):
        """Should search stored documents by word and return results."""
        # Store some documents first
        text_processor.analyze_text(sample_texts['complex'], store_result=True)
        text_processor.analyze_text(sample_texts['positive'], store_result=True)
        
        # Search for a word
        response = client.get('/api/text/search?word=text',
                             headers=authenticated_user['headers'])
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert data['word'] == 'text'
        assert 'results_count' in data
        assert 'results' in data
        assert isinstance(data['results'], list)
    
    def test_requires_search_word_parameter(self, client, authenticated_user):
        """Should require word parameter for search."""
        response = client.get('/api/text/search',
                             headers=authenticated_user['headers'])
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Search word parameter is required' in data['error']


class TestPerformanceBenchmarking:
    """Test endpoint performance benchmarking functionality."""
    
    def test_benchmark_endpoint_measures_performance(self, test_app):
        """Should measure endpoint performance accurately."""
        stats = benchmark_endpoint(test_app, '/health', iterations=5)
        
        assert 'min_time' in stats
        assert 'max_time' in stats
        assert 'avg_time' in stats
        assert 'total_time' in stats
        
        assert stats['min_time'] >= 0
        assert stats['max_time'] >= stats['min_time']
        assert stats['avg_time'] >= stats['min_time']
        assert stats['avg_time'] <= stats['max_time']
    
    def test_benchmark_post_endpoint_with_data(self, test_app, sample_user_data):
        """Should benchmark POST endpoints with data."""
        stats = benchmark_endpoint(
            test_app, 
            '/api/auth/register',
            data=sample_user_data,
            iterations=3
        )
        
        assert stats['avg_time'] > 0
        assert stats['total_time'] >= stats['avg_time']


class TestAnalyticsEndpoint:
    """Test analytics endpoint behavior and statistics collection."""
    
    def test_returns_system_analytics(self, client, authenticated_user):
        """Should return comprehensive system analytics and statistics."""
        response = client.get('/api/analytics/stats',
                             headers=authenticated_user['headers'])
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        stats = data['stats']
        
        # Verify analytics structure
        assert 'users' in stats
        assert 'documents' in stats
        assert 'sessions' in stats
        
        # Verify user stats
        assert 'total' in stats['users']
        assert 'active_monthly' in stats['users']
        
        # Verify document stats
        assert 'total' in stats['documents']
        assert 'avg_word_count' in stats['documents']
        
        # Verify session stats
        assert 'total' in stats['sessions']
        assert 'active' in stats['sessions']


class TestConcurrentRequestHandling:
    """Test concurrent request handling and thread safety."""
    
    def test_handles_concurrent_registrations(self, test_app, data_generator):
        """Should handle multiple concurrent user registrations safely."""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def register_user(app, user_data):
            with app.test_client() as client:
                response = client.post('/api/auth/register',
                                      json=user_data,
                                      content_type='application/json')
                results_queue.put((response.status_code, response.get_json()))
        
        # Create multiple users with different data
        threads = []
        for i in range(5):
            user_data = data_generator.user_data(f"user{i}")
            thread = threading.Thread(target=register_user, args=(test_app, user_data))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        assert len(results) == 5
        
        # All registrations should succeed with unique users
        success_count = sum(1 for status, data in results if status == 201)
        assert success_count == 5


class TestRequestValidation:
    """Test request validation and data sanitization."""
    
    def test_validates_json_content_type(self, client, sample_user_data):
        """Should validate JSON content type for endpoints requiring JSON."""
        # Send data without proper content type
        response = client.post('/api/auth/register',
                              data=json.dumps(sample_user_data))
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'JSON data required' in data['error']
    
    def test_sanitizes_input_data(self, client, authenticated_user):
        """Should sanitize and validate input data properly."""
        # Test with potentially malicious input
        malicious_text = "<script>alert('xss')</script>Normal text content"
        text_data = {'text': malicious_text}
        
        response = client.post('/api/text/analyze',
                              json=text_data,
                              headers=authenticated_user['headers'])
        
        # Should process without issues (actual sanitization depends on text processor)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True


@pytest.mark.integration
class TestEndpointIntegration:
    """Test integration between multiple endpoints and services."""
    
    def test_complete_user_workflow(self, client, sample_user_data, sample_texts):
        """Should support complete user workflow from registration to text analysis."""
        # 1. Register user
        response = client.post('/api/auth/register',
                              json=sample_user_data,
                              content_type='application/json')
        assert response.status_code == 201
        
        user_data = response.get_json()
        headers = {'Authorization': f"Bearer {user_data['session_token']}"}
        
        # 2. Verify profile access
        response = client.get('/api/auth/profile', headers=headers)
        assert response.status_code == 200
        
        # 3. Analyze text
        text_data = {'text': sample_texts['complex']}
        response = client.post('/api/text/analyze',
                              json=text_data,
                              headers=headers)
        assert response.status_code == 200
        
        # 4. Search documents
        response = client.get('/api/text/search?word=analysis', headers=headers)
        assert response.status_code == 200
        
        # 5. Get analytics
        response = client.get('/api/analytics/stats', headers=headers)
        assert response.status_code == 200
    
    def test_session_validation_workflow(self, client, sample_user_data):
        """Should validate session tokens consistently across endpoints."""
        # Register and get session token
        response = client.post('/api/auth/register',
                              json=sample_user_data,
                              content_type='application/json')
        session_token = response.get_json()['session_token']
        
        # Validate session token
        validate_data = {'session_token': session_token}
        response = client.post('/api/auth/validate',
                              json=validate_data,
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['valid'] is True
        assert data['user_id'] is not None
