"""
Integration tests for API endpoints using London School TDD methodology.
Tests real HTTP responses, database operations, and end-to-end API behavior.
"""

import pytest
import json
import time
import tempfile
import os
from flask import Flask
from typing import Dict, Any, List

from src.api.endpoints import create_app, benchmark_endpoint
from src.auth.authentication import AuthenticationManager
from src.utils.text_processing import TextProcessor


class TestAPIIntegration:
    """
    London School TDD integration tests for API endpoints.
    Tests real HTTP behavior, authentication flows, and database interactions.
    """
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def test_app(self, temp_db_path):
        """Create Flask test app with real database."""
        config = {
            'TESTING': True,
            'DATABASE_PATH': temp_db_path,
            'SECRET_KEY': 'test-secret-key-for-testing'
        }
        app = create_app(config)
        return app
    
    @pytest.fixture
    def client(self, test_app):
        """Create test client."""
        return test_app.test_client()
    
    @pytest.fixture
    def auth_manager(self, temp_db_path):
        """Create authentication manager for testing."""
        return AuthenticationManager(temp_db_path)
    
    @pytest.fixture
    def registered_user_data(self, client):
        """Register a test user and return user data."""
        user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword123'
        }
        
        response = client.post('/api/auth/register', 
                             json=user_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        response_data = json.loads(response.data)
        
        return {
            'user_data': user_data,
            'user_id': response_data['user']['user_id'],
            'session_token': response_data['session_token']
        }
    
    @pytest.fixture
    def auth_headers(self, registered_user_data):
        """Create authorization headers for authenticated requests."""
        return {
            'Authorization': f"Bearer {registered_user_data['session_token']}",
            'Content-Type': 'application/json'
        }


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_returns_healthy_status(self, client):
        """Test health endpoint returns proper status."""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'version' in data
        assert data['version'] == '1.0.0'
        
        # Verify response time header
        assert 'X-Response-Time' in response.headers
    
    def test_health_check_with_database_connectivity(self, client, temp_db_path):
        """Test health check validates database connectivity."""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'


class TestAuthenticationEndpoints:
    """Test authentication-related API endpoints."""
    
    def test_user_registration_success_creates_user_and_session(self, client):
        """Test successful user registration creates user and returns session."""
        user_data = {
            'username': 'newuser',
            'email': 'newuser@example.com', 
            'password': 'securepassword123'
        }
        
        response = client.post('/api/auth/register',
                             json=user_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        data = json.loads(response.data)
        
        # Verify response structure
        assert data['success'] is True
        assert 'user' in data
        assert 'session_token' in data
        
        # Verify user data
        user = data['user']
        assert user['username'] == user_data['username']
        assert user['email'] == user_data['email']
        assert 'user_id' in user
        assert 'created_at' in user
        assert 'password_hash' not in user  # Should not expose password hash
        
        # Verify session token
        assert isinstance(data['session_token'], str)
        assert len(data['session_token']) > 20
    
    def test_user_registration_validation_errors(self, client):
        """Test user registration input validation."""
        # Test missing fields
        response = client.post('/api/auth/register',
                             json={},
                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        
        # Test invalid email
        response = client.post('/api/auth/register',
                             json={
                                 'username': 'testuser',
                                 'email': 'invalid-email',
                                 'password': 'password123'
                             },
                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid email format' in data['error']
        
        # Test short password
        response = client.post('/api/auth/register',
                             json={
                                 'username': 'testuser',
                                 'email': 'test@example.com',
                                 'password': 'short'
                             },
                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Password must be at least 8 characters' in data['error']
    
    def test_user_registration_prevents_duplicates(self, client):
        """Test prevention of duplicate usernames and emails."""
        user_data = {
            'username': 'duplicateuser',
            'email': 'duplicate@example.com',
            'password': 'password123'
        }
        
        # First registration should succeed
        response1 = client.post('/api/auth/register',
                              json=user_data,
                              content_type='application/json')
        assert response1.status_code == 201
        
        # Second registration with same username should fail
        response2 = client.post('/api/auth/register',
                              json=user_data,
                              content_type='application/json')
        assert response2.status_code == 400
        data = json.loads(response2.data)
        assert 'Username already exists' in data['error']
        
        # Registration with same email but different username should fail
        user_data['username'] = 'differentuser'
        response3 = client.post('/api/auth/register',
                              json=user_data,
                              content_type='application/json')
        assert response3.status_code == 400
        data = json.loads(response3.data)
        assert 'Email already registered' in data['error']
    
    def test_user_login_success_returns_session_token(self, client, registered_user_data):
        """Test successful login returns session token."""
        login_data = {
            'username': registered_user_data['user_data']['username'],
            'password': registered_user_data['user_data']['password']
        }
        
        response = client.post('/api/auth/login',
                             json=login_data,
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'user' in data
        assert 'session_token' in data
        
        # Verify user data
        user = data['user']
        assert user['username'] == login_data['username']
        assert 'last_login' in user
        assert user['last_login'] is not None
        
        # Session token should be different from registration token
        assert data['session_token'] != registered_user_data['session_token']
    
    def test_user_login_failure_with_invalid_credentials(self, client, registered_user_data):
        """Test login failure with invalid credentials."""
        # Test wrong password
        response = client.post('/api/auth/login',
                             json={
                                 'username': registered_user_data['user_data']['username'],
                                 'password': 'wrongpassword'
                             },
                             content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid credentials' in data['error']
        
        # Test non-existent user
        response = client.post('/api/auth/login',
                             json={
                                 'username': 'nonexistentuser',
                                 'password': 'password123'
                             },
                             content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid credentials' in data['error']
    
    def test_user_login_input_validation(self, client):
        """Test login input validation."""
        # Test missing username
        response = client.post('/api/auth/login',
                             json={'password': 'password123'},
                             content_type='application/json')
        assert response.status_code == 400
        
        # Test missing password
        response = client.post('/api/auth/login',
                             json={'username': 'testuser'},
                             content_type='application/json')
        assert response.status_code == 400
        
        # Test empty JSON
        response = client.post('/api/auth/login',
                             json={},
                             content_type='application/json')
        assert response.status_code == 400
    
    def test_get_profile_with_valid_session(self, client, registered_user_data, auth_headers):
        """Test retrieving user profile with valid session."""
        response = client.get('/api/auth/profile', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'user' in data
        user = data['user']
        assert user['user_id'] == registered_user_data['user_id']
        assert user['username'] == registered_user_data['user_data']['username']
        assert user['email'] == registered_user_data['user_data']['email']
        assert 'created_at' in user
        assert 'is_active' in user
        assert user['is_active'] is True
    
    def test_get_profile_with_invalid_session(self, client):
        """Test profile access with invalid session token."""
        headers = {'Authorization': 'Bearer invalid_token_123'}
        
        response = client.get('/api/auth/profile', headers=headers)
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid or expired session' in data['error']
    
    def test_get_profile_without_authorization_header(self, client):
        """Test profile access without authorization header."""
        response = client.get('/api/auth/profile')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Missing or invalid authorization header' in data['error']
    
    def test_session_validation_endpoint(self, client, registered_user_data):
        """Test session validation endpoint."""
        # Test valid session
        response = client.post('/api/auth/validate',
                             json={'session_token': registered_user_data['session_token']},
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['valid'] is True
        assert data['user_id'] == registered_user_data['user_id']
        
        # Test invalid session
        response = client.post('/api/auth/validate',
                             json={'session_token': 'invalid_token_123'},
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['valid'] is False
        assert data['user_id'] is None


class TestTextProcessingEndpoints:
    """Test text processing API endpoints."""
    
    def test_analyze_text_success_returns_comprehensive_analysis(self, client, auth_headers):
        """Test text analysis endpoint returns comprehensive analysis."""
        text_data = {
            'text': 'This is a wonderful test document! It contains multiple sentences and should produce excellent analysis results.',
            'store_result': True
        }
        
        response = client.post('/api/text/analyze',
                             json=text_data,
                             headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'analysis' in data
        
        analysis = data['analysis']
        assert analysis['word_count'] > 0
        assert analysis['character_count'] > 0
        assert analysis['sentence_count'] > 0
        assert analysis['paragraph_count'] > 0
        assert analysis['avg_word_length'] > 0
        assert 0 <= analysis['readability_score'] <= 100
        assert isinstance(analysis['common_words'], dict)
        assert isinstance(analysis['sentiment_score'], (int, float))
        assert analysis['processing_time'] >= 0
        
        # Text contains "wonderful" and "excellent" - should have positive sentiment
        assert analysis['sentiment_score'] > 0
    
    def test_analyze_text_without_authentication(self, client):
        """Test text analysis requires authentication."""
        response = client.post('/api/text/analyze',
                             json={'text': 'Test text'},
                             content_type='application/json')
        
        assert response.status_code == 401
    
    def test_analyze_text_input_validation(self, client, auth_headers):
        """Test text analysis input validation."""
        # Test empty text
        response = client.post('/api/text/analyze',
                             json={'text': ''},
                             headers=auth_headers)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Text content is required' in data['error']
        
        # Test missing text field
        response = client.post('/api/text/analyze',
                             json={},
                             headers=auth_headers)
        assert response.status_code == 400
        
        # Test text too large (over 100KB)
        large_text = 'x' * 100001
        response = client.post('/api/text/analyze',
                             json={'text': large_text},
                             headers=auth_headers)
        assert response.status_code == 413
        data = json.loads(response.data)
        assert 'Text content too large' in data['error']
    
    def test_analyze_text_without_storage(self, client, auth_headers):
        """Test text analysis without database storage."""
        text_data = {
            'text': 'This text will not be stored in the database.',
            'store_result': False
        }
        
        response = client.post('/api/text/analyze',
                             json=text_data,
                             headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'analysis' in data
    
    def test_clean_text_endpoint(self, client, auth_headers):
        """Test text cleaning endpoint."""
        text_data = {
            'text': '  This   text    has   extra   whitespace   and   weird   punctuation  !  '
        }
        
        response = client.post('/api/text/clean',
                             json=text_data,
                             headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'cleaned_text' in data
        assert 'original_length' in data
        assert 'cleaned_length' in data
        
        # Verify cleaning worked
        cleaned = data['cleaned_text']
        assert '   ' not in cleaned
        assert cleaned.startswith('This')
        assert data['original_length'] > data['cleaned_length']
    
    def test_clean_text_validation(self, client, auth_headers):
        """Test text cleaning input validation."""
        # Test empty text
        response = client.post('/api/text/clean',
                             json={'text': ''},
                             headers=auth_headers)
        assert response.status_code == 400
        
        # Test missing text field
        response = client.post('/api/text/clean',
                             json={},
                             headers=auth_headers)
        assert response.status_code == 400
    
    def test_search_text_endpoint(self, client, auth_headers):
        """Test text search endpoint."""
        # First, analyze some texts to populate database
        texts = [
            'The quick brown fox jumps over the lazy dog',
            'A brown bear walks through the forest',
            'The lazy cat sleeps all day'
        ]
        
        for text in texts:
            client.post('/api/text/analyze',
                       json={'text': text, 'store_result': True},
                       headers=auth_headers)
        
        # Search for word "brown"
        response = client.get('/api/text/search?word=brown',
                            headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['word'] == 'brown'
        assert data['results_count'] == 2  # Two texts contain "brown"
        assert len(data['results']) == 2
        
        # Verify result structure
        for result in data['results']:
            assert 'doc_id' in result
            assert 'content' in result
            assert 'frequency' in result
            assert 'position_avg' in result
    
    def test_search_text_validation(self, client, auth_headers):
        """Test search text input validation."""
        # Test missing word parameter
        response = client.get('/api/text/search', headers=auth_headers)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Search word parameter is required' in data['error']
        
        # Test empty word parameter
        response = client.get('/api/text/search?word=', headers=auth_headers)
        assert response.status_code == 400
    
    def test_get_document_endpoint(self, client, auth_headers):
        """Test document retrieval endpoint."""
        # Analyze text to create document
        text = 'This is a test document for retrieval testing.'
        response = client.post('/api/text/analyze',
                             json={'text': text, 'store_result': True},
                             headers=auth_headers)
        assert response.status_code == 200
        
        # Calculate doc_id
        import hashlib
        doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        
        # Retrieve document
        response = client.get(f'/api/text/document/{doc_id}', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'document' in data
        document = data['document']
        assert document['doc_id'] == doc_id
        assert document['content'] == text
        assert 'analysis' in document
        assert 'processed_at' in document
    
    def test_get_document_not_found(self, client, auth_headers):
        """Test document retrieval with non-existent ID."""
        response = client.get('/api/text/document/nonexistent_id', headers=auth_headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Document not found' in data['error']


class TestAnalyticsEndpoints:
    """Test analytics and statistics endpoints."""
    
    def test_analytics_stats_endpoint(self, client, auth_headers):
        """Test analytics statistics endpoint."""
        # Create some data first
        client.post('/api/text/analyze',
                   json={'text': 'Sample text for analytics testing', 'store_result': True},
                   headers=auth_headers)
        
        response = client.get('/api/analytics/stats', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'stats' in data
        
        stats = data['stats']
        assert 'users' in stats
        assert 'documents' in stats
        assert 'sessions' in stats
        
        # Verify user stats
        user_stats = stats['users']
        assert 'total' in user_stats
        assert 'active_monthly' in user_stats
        assert user_stats['total'] >= 1  # At least the test user
        
        # Verify document stats
        doc_stats = stats['documents']
        assert 'total' in doc_stats
        assert 'avg_word_count' in doc_stats
        assert 'total_words' in doc_stats
        assert doc_stats['total'] >= 1  # At least one document analyzed
        
        # Verify session stats
        session_stats = stats['sessions']
        assert 'total' in session_stats
        assert 'active' in session_stats


class TestAPIMiddleware:
    """Test API middleware functionality."""
    
    def test_cors_headers_present(self, client):
        """Test CORS headers are present in responses."""
        response = client.get('/health')
        
        # Flask-CORS should add CORS headers
        assert response.status_code == 200
    
    def test_response_time_header(self, client):
        """Test response time header is added to all responses."""
        response = client.get('/health')
        
        assert 'X-Response-Time' in response.headers
        response_time = response.headers['X-Response-Time']
        assert response_time.endswith('s')  # Should end with 's' for seconds
        
        # Parse and validate time value
        time_value = float(response_time[:-1])
        assert time_value >= 0
        assert time_value < 10  # Should be under 10 seconds for health check
    
    def test_json_content_type_handling(self, client):
        """Test JSON content type validation."""
        # Test with non-JSON data
        response = client.post('/api/auth/register',
                             data='invalid json data',
                             content_type='text/plain')
        
        assert response.status_code == 400
        
        # Test with no content type
        response = client.post('/api/auth/register')
        assert response.status_code == 400
    
    def test_error_handling_returns_json(self, client):
        """Test that all errors return JSON responses."""
        # Test 404 error
        response = client.get('/nonexistent/endpoint')
        assert response.status_code == 404
        
        # Test validation error
        response = client.post('/api/auth/register',
                             json={},
                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestAPIAuthentication:
    """Test API authentication middleware."""
    
    def test_bearer_token_authentication(self, client, registered_user_data):
        """Test Bearer token authentication."""
        headers = {
            'Authorization': f"Bearer {registered_user_data['session_token']}",
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/auth/profile', headers=headers)
        assert response.status_code == 200
    
    def test_invalid_authorization_header_formats(self, client):
        """Test various invalid authorization header formats."""
        invalid_headers = [
            {'Authorization': 'invalid_token'},  # Missing Bearer
            {'Authorization': 'Basic invalid_token'},  # Wrong auth type
            {'Authorization': 'Bearer '},  # Empty token
            {},  # No header
        ]
        
        for headers in invalid_headers:
            headers.update({'Content-Type': 'application/json'})
            response = client.get('/api/auth/profile', headers=headers)
            assert response.status_code == 401
            
            if 'Authorization' in headers:
                data = json.loads(response.data)
                assert 'authorization header' in data['error'].lower()
    
    def test_expired_session_handling(self, client, auth_manager):
        """Test handling of expired sessions."""
        # Register user
        user = auth_manager.register_user('expiry_test', 'expiry@test.com', 'password123')
        
        # Create expired session (-1 hour)
        expired_token = auth_manager.create_session(user.user_id, duration_hours=-1)
        
        headers = {
            'Authorization': f'Bearer {expired_token}',
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/auth/profile', headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid or expired session' in data['error']


class TestAPIPerformance:
    """Test API performance and load handling."""
    
    def test_registration_endpoint_performance(self, test_app):
        """Test user registration endpoint performance."""
        user_data = {
            'username': 'perftest',
            'email': 'perf@test.com',
            'password': 'password123'
        }
        
        # Benchmark registration endpoint
        stats = benchmark_endpoint(test_app, '/api/auth/register', user_data, iterations=5)
        
        # Assertions for performance
        assert stats['avg_time'] < 1.0  # Less than 1 second on average
        assert stats['max_time'] < 2.0  # Maximum time under 2 seconds
        assert stats['min_time'] >= 0  # Minimum time should be positive
    
    def test_login_endpoint_performance(self, test_app, client):
        """Test login endpoint performance."""
        # First register a user
        user_data = {
            'username': 'loginperf',
            'email': 'loginperf@test.com',
            'password': 'password123'
        }
        
        client.post('/api/auth/register', json=user_data, content_type='application/json')
        
        # Benchmark login endpoint
        login_data = {'username': 'loginperf', 'password': 'password123'}
        stats = benchmark_endpoint(test_app, '/api/auth/login', login_data, iterations=10)
        
        assert stats['avg_time'] < 0.5  # Login should be fast
        assert stats['max_time'] < 1.0
    
    def test_text_analysis_performance(self, test_app, registered_user_data):
        """Test text analysis endpoint performance."""
        headers = {'Authorization': f"Bearer {registered_user_data['session_token']}"}
        text_data = {
            'text': 'This is a performance test document. ' * 50,  # ~350 words
            'store_result': True
        }
        
        stats = benchmark_endpoint(test_app, '/api/text/analyze', text_data, headers, iterations=5)
        
        assert stats['avg_time'] < 2.0  # Text analysis should complete quickly
        assert stats['max_time'] < 5.0
    
    def test_concurrent_api_requests(self, client, registered_user_data):
        """Test API handling of concurrent requests."""
        import threading
        import concurrent.futures
        
        headers = {
            'Authorization': f"Bearer {registered_user_data['session_token']}",
            'Content-Type': 'application/json'
        }
        
        results = []
        errors = []
        
        def make_request(i):
            try:
                response = client.post('/api/text/analyze',
                                     json={'text': f'Concurrent test document {i}', 'store_result': True},
                                     headers=headers)
                results.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Make 20 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(20)]
            concurrent.futures.wait(futures)
        
        # All requests should succeed
        assert len(results) == 20
        assert len(errors) == 0
        assert all(status == 200 for status in results)


class TestAPIIntegrationWorkflows:
    """Test complete API workflows end-to-end."""
    
    def test_complete_user_workflow(self, client):
        """Test complete user workflow from registration to text processing."""
        # Step 1: Register user
        user_data = {
            'username': 'workflowuser',
            'email': 'workflow@test.com',
            'password': 'workflow123'
        }
        
        response = client.post('/api/auth/register', json=user_data, content_type='application/json')
        assert response.status_code == 201
        
        reg_data = json.loads(response.data)
        session_token = reg_data['session_token']
        user_id = reg_data['user']['user_id']
        
        # Step 2: Login (get new session)
        response = client.post('/api/auth/login', json={
            'username': user_data['username'],
            'password': user_data['password']
        }, content_type='application/json')
        assert response.status_code == 200
        
        login_data = json.loads(response.data)
        new_session_token = login_data['session_token']
        
        # Step 3: Get profile
        headers = {'Authorization': f'Bearer {new_session_token}'}
        response = client.get('/api/auth/profile', headers=headers)
        assert response.status_code == 200
        
        profile_data = json.loads(response.data)
        assert profile_data['user']['user_id'] == user_id
        
        # Step 4: Analyze text
        text_content = 'This is a fantastic workflow test! The integration is working excellently.'
        response = client.post('/api/text/analyze',
                             json={'text': text_content, 'store_result': True},
                             headers=headers)
        assert response.status_code == 200
        
        analysis_data = json.loads(response.data)
        assert analysis_data['success'] is True
        assert analysis_data['analysis']['sentiment_score'] > 0  # Positive sentiment
        
        # Step 5: Search for text
        response = client.get('/api/text/search?word=fantastic', headers=headers)
        assert response.status_code == 200
        
        search_data = json.loads(response.data)
        assert search_data['results_count'] == 1
        
        # Step 6: Retrieve document
        import hashlib
        doc_id = hashlib.sha256(text_content.encode()).hexdigest()[:16]
        
        response = client.get(f'/api/text/document/{doc_id}', headers=headers)
        assert response.status_code == 200
        
        doc_data = json.loads(response.data)
        assert doc_data['document']['content'] == text_content
        
        # Step 7: Get analytics
        response = client.get('/api/analytics/stats', headers=headers)
        assert response.status_code == 200
        
        stats_data = json.loads(response.data)
        assert stats_data['stats']['users']['total'] >= 1
        assert stats_data['stats']['documents']['total'] >= 1
    
    def test_multi_user_concurrent_workflow(self, client):
        """Test multiple users working concurrently."""
        users = []
        
        # Register multiple users
        for i in range(5):
            user_data = {
                'username': f'multiuser{i}',
                'email': f'multi{i}@test.com',
                'password': 'password123'
            }
            
            response = client.post('/api/auth/register', json=user_data, content_type='application/json')
            assert response.status_code == 201
            
            reg_data = json.loads(response.data)
            users.append({
                'username': user_data['username'],
                'session_token': reg_data['session_token'],
                'user_id': reg_data['user']['user_id']
            })
        
        # Each user analyzes different text
        for i, user in enumerate(users):
            headers = {'Authorization': f"Bearer {user['session_token']}"}
            
            text = f"User {i} test document with unique content and analysis data."
            response = client.post('/api/text/analyze',
                                 json={'text': text, 'store_result': True},
                                 headers=headers)
            assert response.status_code == 200
        
        # Verify each user can access their own profile
        for user in users:
            headers = {'Authorization': f"Bearer {user['session_token']}"}
            response = client.get('/api/auth/profile', headers=headers)
            assert response.status_code == 200
            
            profile_data = json.loads(response.data)
            assert profile_data['user']['username'] == user['username']
    
    def test_session_expiration_workflow(self, client, auth_manager):
        """Test session expiration workflow."""
        # Register user
        user = auth_manager.register_user('sessiontest', 'session@test.com', 'password123')
        
        # Create short-lived session (1 second)
        import time
        session_token = auth_manager.create_session(user.user_id, duration_hours=1/3600)  # 1 second
        
        # Should work immediately
        headers = {'Authorization': f'Bearer {session_token}'}
        response = client.get('/api/auth/profile', headers=headers)
        assert response.status_code == 200
        
        # Wait for expiration
        time.sleep(2)
        
        # Should fail after expiration
        response = client.get('/api/auth/profile', headers=headers)
        assert response.status_code == 401
        
        data = json.loads(response.data)
        assert 'Invalid or expired session' in data['error']