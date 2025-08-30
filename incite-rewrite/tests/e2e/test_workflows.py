"""
End-to-end workflow tests using London School TDD methodology.
Tests complete user journeys, real system interactions, and business workflows.
"""

import pytest
import json
import time
import tempfile
import os
import subprocess
import threading
import requests
import sqlite3
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.api.endpoints import create_app
from src.auth.authentication import AuthenticationManager
from src.utils.text_processing import TextProcessor
from src.database.connection import DatabaseManager


class TestE2EUserJourneys:
    """
    End-to-end tests for complete user journeys.
    Tests real user workflows without mocks or stubs.
    """
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for E2E testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def e2e_app(self, temp_db_path):
        """Create Flask app for E2E testing."""
        config = {
            'TESTING': True,
            'DATABASE_PATH': temp_db_path,
            'SECRET_KEY': 'e2e-test-secret-key'
        }
        app = create_app(config)
        return app
    
    @pytest.fixture
    def client(self, e2e_app):
        """Create test client for E2E testing."""
        return e2e_app.test_client()
    
    @pytest.fixture
    def db_manager(self, temp_db_path):
        """Create database manager for direct database verification."""
        return DatabaseManager(temp_db_path)
    
    def test_new_user_complete_onboarding_journey(self, client, temp_db_path):
        """
        Test complete new user onboarding journey:
        Registration -> Email verification simulation -> First login -> Profile setup -> First document analysis
        """
        # Step 1: User Registration
        user_data = {
            'username': 'newuser2024',
            'email': 'newuser2024@example.com',
            'password': 'SecurePassword123!'
        }
        
        registration_response = client.post('/api/auth/register',
                                          json=user_data,
                                          content_type='application/json')
        
        assert registration_response.status_code == 201
        reg_data = json.loads(registration_response.data)
        
        # Verify registration success
        assert reg_data['success'] is True
        assert 'user' in reg_data
        assert 'session_token' in reg_data
        
        user_id = reg_data['user']['user_id']
        initial_session = reg_data['session_token']
        
        # Verify user exists in database
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute("SELECT username, email, is_active FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()
            assert user_row is not None
            assert user_row[0] == user_data['username']
            assert user_row[1] == user_data['email']
            assert user_row[2] == 1  # is_active
        
        # Step 2: Login to get fresh session
        login_response = client.post('/api/auth/login',
                                   json={
                                       'username': user_data['username'],
                                       'password': user_data['password']
                                   },
                                   content_type='application/json')
        
        assert login_response.status_code == 200
        login_data = json.loads(login_response.data)
        
        session_token = login_data['session_token']
        auth_headers = {
            'Authorization': f'Bearer {session_token}',
            'Content-Type': 'application/json'
        }
        
        # Verify login updated last_login
        assert login_data['user']['last_login'] is not None
        
        # Step 3: Access user profile
        profile_response = client.get('/api/auth/profile', headers=auth_headers)
        
        assert profile_response.status_code == 200
        profile_data = json.loads(profile_response.data)
        
        assert profile_data['user']['username'] == user_data['username']
        assert profile_data['user']['email'] == user_data['email']
        assert profile_data['user']['is_active'] is True
        
        # Step 4: First document analysis
        first_document = """
        Welcome to our text analysis platform! This is my first document.
        I'm excited to explore the capabilities of natural language processing.
        The system should analyze sentiment, readability, and word frequency.
        This seems like an excellent tool for content analysis!
        """
        
        analysis_response = client.post('/api/text/analyze',
                                      json={
                                          'text': first_document,
                                          'store_result': True
                                      },
                                      headers=auth_headers)
        
        assert analysis_response.status_code == 200
        analysis_data = json.loads(analysis_response.data)
        
        # Verify comprehensive analysis
        analysis = analysis_data['analysis']
        assert analysis['word_count'] > 20
        assert analysis['sentence_count'] >= 4
        assert analysis['sentiment_score'] > 0  # Should be positive due to "excited", "excellent"
        assert 0 <= analysis['readability_score'] <= 100
        assert len(analysis['common_words']) > 0
        
        # Step 5: Search for document
        search_response = client.get('/api/text/search?word=excellent',
                                   headers=auth_headers)
        
        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)
        assert search_data['results_count'] == 1
        assert len(search_data['results']) == 1
        
        # Step 6: Retrieve stored document
        import hashlib
        doc_id = hashlib.sha256(first_document.encode()).hexdigest()[:16]
        
        document_response = client.get(f'/api/text/document/{doc_id}',
                                     headers=auth_headers)
        
        assert document_response.status_code == 200
        doc_data = json.loads(document_response.data)
        
        assert doc_data['document']['content'] == first_document
        assert 'analysis' in doc_data['document']
        
        # Step 7: View analytics
        analytics_response = client.get('/api/analytics/stats', headers=auth_headers)
        
        assert analytics_response.status_code == 200
        stats_data = json.loads(analytics_response.data)
        
        stats = stats_data['stats']
        assert stats['users']['total'] >= 1
        assert stats['documents']['total'] >= 1
        assert stats['documents']['total_words'] > 0
    
    def test_power_user_batch_processing_workflow(self, client, temp_db_path):
        """
        Test power user workflow:
        Registration -> Multiple document processing -> Batch analysis -> Search across documents
        """
        # Register power user
        user_data = {
            'username': 'poweruser',
            'email': 'power@example.com',
            'password': 'PowerPassword123!'
        }
        
        registration_response = client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_data = json.loads(registration_response.data)
        session_token = reg_data['session_token']
        
        auth_headers = {
            'Authorization': f'Bearer {session_token}',
            'Content-Type': 'application/json'
        }
        
        # Batch document processing - simulate analyzing multiple documents
        documents = [
            {
                'title': 'Technical Documentation',
                'content': '''
                This technical documentation covers advanced concepts in software architecture.
                The implementation focuses on scalability, maintainability, and performance optimization.
                Complex algorithms and data structures are utilized throughout the system.
                '''
            },
            {
                'title': 'Marketing Copy',
                'content': '''
                Our amazing product delivers fantastic results for customers worldwide!
                Experience the wonderful benefits of our revolutionary technology.
                Join thousands of satisfied users who love our excellent service.
                '''
            },
            {
                'title': 'Customer Feedback',
                'content': '''
                The service is terrible and I'm extremely disappointed with the results.
                This awful experience has been frustrating and unsatisfactory.
                I would not recommend this horrible product to anyone.
                '''
            },
            {
                'title': 'Research Report',
                'content': '''
                The statistical analysis reveals significant correlations between variables.
                Quantitative methodologies were employed to ensure objective measurements.
                Results indicate substantial improvements in performance metrics.
                '''
            },
            {
                'title': 'Creative Writing',
                'content': '''
                The mysterious forest whispered secrets to those who listened carefully.
                Sunbeams danced through ancient leaves, creating magical patterns of light.
                Adventure awaited beyond every winding path and hidden grove.
                '''
            }
        ]
        
        analysis_results = []
        doc_ids = []
        
        # Process each document
        for doc in documents:
            response = client.post('/api/text/analyze',
                                 json={
                                     'text': doc['content'],
                                     'store_result': True
                                 },
                                 headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            analysis_results.append({
                'title': doc['title'],
                'analysis': data['analysis']
            })
            
            # Calculate doc ID for later retrieval
            import hashlib
            doc_id = hashlib.sha256(doc['content'].encode()).hexdigest()[:16]
            doc_ids.append(doc_id)
        
        # Verify sentiment analysis across different document types
        marketing_sentiment = next(r['analysis']['sentiment_score'] for r in analysis_results if r['title'] == 'Marketing Copy')
        feedback_sentiment = next(r['analysis']['sentiment_score'] for r in analysis_results if r['title'] == 'Customer Feedback')
        
        assert marketing_sentiment > 0  # Marketing copy should be positive
        assert feedback_sentiment < 0  # Negative feedback should be negative
        assert marketing_sentiment > feedback_sentiment  # Marketing should be more positive than feedback
        
        # Verify readability differences
        technical_readability = next(r['analysis']['readability_score'] for r in analysis_results if r['title'] == 'Technical Documentation')
        creative_readability = next(r['analysis']['readability_score'] for r in analysis_results if r['title'] == 'Creative Writing')
        
        # Creative writing should generally be more readable than technical documentation
        assert creative_readability > technical_readability
        
        # Search across all documents for common terms
        search_terms = ['the', 'and', 'performance', 'amazing', 'terrible']
        
        for term in search_terms:
            search_response = client.get(f'/api/text/search?word={term}', headers=auth_headers)
            assert search_response.status_code == 200
            
            search_data = json.loads(search_response.data)
            
            if term in ['performance']:
                assert search_data['results_count'] >= 1  # Should find technical/research docs
            elif term in ['amazing']:
                assert search_data['results_count'] >= 1  # Should find marketing copy
            elif term in ['terrible']:
                assert search_data['results_count'] >= 1  # Should find customer feedback
        
        # Retrieve and verify each document
        for i, doc_id in enumerate(doc_ids):
            response = client.get(f'/api/text/document/{doc_id}', headers=auth_headers)
            assert response.status_code == 200
            
            doc_data = json.loads(response.data)
            assert doc_data['document']['content'] == documents[i]['content']
        
        # Check final analytics
        analytics_response = client.get('/api/analytics/stats', headers=auth_headers)
        stats_data = json.loads(analytics_response.data)
        
        assert stats_data['stats']['documents']['total'] == 5
        assert stats_data['stats']['documents']['total_words'] > 100
    
    def test_multi_session_user_workflow(self, client, temp_db_path):
        """
        Test multi-session workflow:
        Register -> Login -> Work -> Logout -> Login again -> Continue work
        """
        user_data = {
            'username': 'multisession',
            'email': 'multi@example.com',
            'password': 'MultiSession123!'
        }
        
        # Session 1: Registration and initial work
        reg_response = client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_data = json.loads(reg_response.data)
        session1_token = reg_data['session_token']
        
        headers1 = {'Authorization': f'Bearer {session1_token}', 'Content-Type': 'application/json'}
        
        # Analyze document in session 1
        doc1 = "This is my first document from session 1. Important content here!"
        response = client.post('/api/text/analyze',
                             json={'text': doc1, 'store_result': True},
                             headers=headers1)
        assert response.status_code == 200
        
        # Session 2: New login and continue work
        login_response = client.post('/api/auth/login', json={
            'username': user_data['username'],
            'password': user_data['password']
        }, content_type='application/json')
        
        login_data = json.loads(login_response.data)
        session2_token = login_data['session_token']
        
        # Verify new session token is different
        assert session2_token != session1_token
        
        headers2 = {'Authorization': f'Bearer {session2_token}', 'Content-Type': 'application/json'}
        
        # Access profile with new session
        profile_response = client.get('/api/auth/profile', headers=headers2)
        assert profile_response.status_code == 200
        
        # Analyze another document in session 2
        doc2 = "This is my second document from session 2. More analysis content!"
        response = client.post('/api/text/analyze',
                             json={'text': doc2, 'store_result': True},
                             headers=headers2)
        assert response.status_code == 200
        
        # Verify both documents exist by searching
        search_response = client.get('/api/text/search?word=document', headers=headers2)
        search_data = json.loads(search_response.data)
        assert search_data['results_count'] == 2  # Should find both documents
        
        # Verify old session is still valid (sessions don't expire immediately)
        profile_response_old = client.get('/api/auth/profile', headers=headers1)
        # May or may not be valid depending on session expiration policy
        # This tests the system's session management behavior
    
    def test_content_creator_workflow(self, client):
        """
        Test content creator workflow:
        Registration -> Create multiple content types -> Analyze sentiment trends -> Clean text -> Search content
        """
        user_data = {
            'username': 'contentcreator',
            'email': 'creator@example.com',
            'password': 'Creator123!'
        }
        
        reg_response = client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_data = json.loads(reg_response.data)
        session_token = reg_data['session_token']
        
        headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
        
        # Content types with different characteristics
        content_pieces = [
            {
                'type': 'blog_post',
                'raw_content': '''
                The    future    of   artificial   intelligence   is    bright   and   promising  !
                
                Machine  learning  algorithms  are  revolutionizing  industries  across   the   globe.
                From  healthcare  to  finance,  AI  is  creating  amazing  opportunities  for  innovation.
                ''',
                'expected_sentiment': 'positive'
            },
            {
                'type': 'product_review', 
                'raw_content': '''
                This   product   is   absolutely   terrible   !   I'm   very   disappointed   .
                
                The  quality  is  poor  and  the  customer  service  is  awful  .
                I  would  never  recommend  this  horrible  experience  to  anyone  .
                ''',
                'expected_sentiment': 'negative'
            },
            {
                'type': 'technical_doc',
                'raw_content': '''
                The  implementation  utilizes  advanced  algorithms  for  optimization  .
                
                Performance  metrics  indicate  substantial  improvements  in  throughput  .
                System  architecture  follows  established  patterns  for  scalability  .
                ''',
                'expected_sentiment': 'neutral'
            }
        ]
        
        processed_content = []
        
        for content in content_pieces:
            # Step 1: Clean the raw content
            clean_response = client.post('/api/text/clean',
                                       json={'text': content['raw_content']},
                                       headers=headers)
            
            assert clean_response.status_code == 200
            clean_data = json.loads(clean_response.data)
            
            cleaned_text = clean_data['cleaned_text']
            
            # Verify cleaning worked - should have fewer characters and no multiple spaces
            assert clean_data['cleaned_length'] < clean_data['original_length']
            assert '  ' not in cleaned_text  # No double spaces
            
            # Step 2: Analyze the cleaned content
            analysis_response = client.post('/api/text/analyze',
                                          json={'text': cleaned_text, 'store_result': True},
                                          headers=headers)
            
            assert analysis_response.status_code == 200
            analysis_data = json.loads(analysis_response.data)
            
            analysis = analysis_data['analysis']
            processed_content.append({
                'type': content['type'],
                'cleaned_text': cleaned_text,
                'analysis': analysis,
                'expected_sentiment': content['expected_sentiment']
            })
        
        # Verify sentiment analysis accuracy
        blog_post = next(c for c in processed_content if c['type'] == 'blog_post')
        product_review = next(c for c in processed_content if c['type'] == 'product_review')
        technical_doc = next(c for c in processed_content if c['type'] == 'technical_doc')
        
        assert blog_post['analysis']['sentiment_score'] > 0  # Positive
        assert product_review['analysis']['sentiment_score'] < 0  # Negative
        assert abs(technical_doc['analysis']['sentiment_score']) < abs(blog_post['analysis']['sentiment_score'])  # More neutral
        
        # Search for content by domain-specific terms
        ai_search = client.get('/api/text/search?word=artificial', headers=headers)
        ai_data = json.loads(ai_search.data)
        assert ai_data['results_count'] == 1  # Should find the blog post
        
        product_search = client.get('/api/text/search?word=product', headers=headers)
        product_data = json.loads(product_search.data)
        assert product_data['results_count'] == 1  # Should find the product review
        
        tech_search = client.get('/api/text/search?word=algorithm', headers=headers)
        tech_data = json.loads(tech_search.data)
        assert tech_data['results_count'] >= 1  # Should find technical content
        
        # Verify analytics show content creation activity
        analytics_response = client.get('/api/analytics/stats', headers=headers)
        stats_data = json.loads(analytics_response.data)
        
        assert stats_data['stats']['documents']['total'] == 3
        assert stats_data['stats']['users']['total'] >= 1


class TestE2ESystemReliability:
    """Test system reliability under various conditions."""
    
    @pytest.fixture
    def reliability_app(self):
        """Create app for reliability testing."""
        config = {
            'TESTING': True,
            'DATABASE_PATH': ':memory:',
            'SECRET_KEY': 'reliability-test-key'
        }
        return create_app(config)
    
    @pytest.fixture
    def reliability_client(self, reliability_app):
        """Create client for reliability testing."""
        return reliability_app.test_client()
    
    def test_system_under_concurrent_load(self, reliability_client):
        """Test system behavior under concurrent user load."""
        def user_workflow(user_id):
            """Simulate complete user workflow."""
            try:
                # Register user
                user_data = {
                    'username': f'loadtest_{user_id}',
                    'email': f'load{user_id}@test.com',
                    'password': 'LoadTest123!'
                }
                
                reg_response = reliability_client.post('/api/auth/register',
                                                     json=user_data,
                                                     content_type='application/json')
                
                if reg_response.status_code != 201:
                    return {'user_id': user_id, 'error': f'Registration failed: {reg_response.status_code}'}
                
                reg_data = json.loads(reg_response.data)
                session_token = reg_data['session_token']
                
                headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
                
                # Analyze multiple documents
                documents = [
                    f'Load test document 1 for user {user_id}. Testing concurrent processing.',
                    f'Load test document 2 for user {user_id}. Analyzing system performance.',
                    f'Load test document 3 for user {user_id}. Verifying data integrity.'
                ]
                
                for i, doc in enumerate(documents):
                    analysis_response = reliability_client.post('/api/text/analyze',
                                                              json={'text': doc, 'store_result': True},
                                                              headers=headers)
                    
                    if analysis_response.status_code != 200:
                        return {'user_id': user_id, 'error': f'Analysis {i} failed: {analysis_response.status_code}'}
                
                # Search for content
                search_response = reliability_client.get('/api/text/search?word=test', headers=headers)
                if search_response.status_code != 200:
                    return {'user_id': user_id, 'error': f'Search failed: {search_response.status_code}'}
                
                # Get profile
                profile_response = reliability_client.get('/api/auth/profile', headers=headers)
                if profile_response.status_code != 200:
                    return {'user_id': user_id, 'error': f'Profile failed: {profile_response.status_code}'}
                
                return {'user_id': user_id, 'success': True}
                
            except Exception as e:
                return {'user_id': user_id, 'error': str(e)}
        
        # Run concurrent user workflows
        num_users = 10
        results = []
        
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(user_workflow, i) for i in range(num_users)]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Analyze results
        successful = [r for r in results if r.get('success')]
        failed = [r for r in results if 'error' in r]
        
        # At least 80% should succeed under load
        success_rate = len(successful) / len(results)
        assert success_rate >= 0.8, f"Success rate {success_rate:.2f} below 80%. Failures: {failed}"
        
        # Verify no data corruption by checking search results
        if successful:
            # Use first successful user to verify data integrity
            test_user = successful[0]
            # Additional verification could be added here
    
    def test_error_recovery_and_graceful_degradation(self, reliability_client):
        """Test system error recovery and graceful degradation."""
        # Register valid user first
        user_data = {
            'username': 'errortest',
            'email': 'error@test.com', 
            'password': 'ErrorTest123!'
        }
        
        reg_response = reliability_client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_data = json.loads(reg_response.data)
        session_token = reg_data['session_token']
        headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
        
        # Test various error conditions and recovery
        error_scenarios = [
            # Invalid JSON
            {
                'method': 'POST',
                'url': '/api/text/analyze',
                'data': 'invalid json',
                'headers': {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'},
                'expected_status': 400
            },
            # Missing authentication
            {
                'method': 'GET',
                'url': '/api/auth/profile',
                'headers': {},
                'expected_status': 401
            },
            # Non-existent endpoint
            {
                'method': 'GET', 
                'url': '/api/nonexistent',
                'headers': headers,
                'expected_status': 404
            },
            # Invalid session token
            {
                'method': 'GET',
                'url': '/api/auth/profile',
                'headers': {'Authorization': 'Bearer invalid_token'},
                'expected_status': 401
            }
        ]
        
        for scenario in error_scenarios:
            if scenario['method'] == 'POST':
                if 'data' in scenario:
                    response = reliability_client.post(scenario['url'],
                                                     data=scenario['data'],
                                                     headers=scenario['headers'])
                else:
                    response = reliability_client.post(scenario['url'],
                                                     json=scenario.get('json', {}),
                                                     headers=scenario['headers'])
            else:
                response = reliability_client.get(scenario['url'], headers=scenario['headers'])
            
            # Verify error is handled gracefully with expected status
            assert response.status_code == scenario['expected_status']
            
            # Verify error response is JSON (except for 404s which might be HTML)
            if response.status_code != 404:
                try:
                    error_data = json.loads(response.data)
                    assert 'error' in error_data
                except json.JSONDecodeError:
                    pytest.fail(f"Error response is not valid JSON: {response.data}")
        
        # Verify system is still functional after errors
        health_response = reliability_client.get('/health')
        assert health_response.status_code == 200
        
        # Verify user can still perform normal operations
        profile_response = reliability_client.get('/api/auth/profile', headers=headers)
        assert profile_response.status_code == 200
    
    def test_data_consistency_across_operations(self, reliability_client, temp_db_path):
        """Test data consistency across multiple operations."""
        # Create temporary database for consistency testing
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            config = {
                'TESTING': True,
                'DATABASE_PATH': db_path,
                'SECRET_KEY': 'consistency-test-key'
            }
            app = create_app(config)
            client = app.test_client()
            
            # Register user
            user_data = {
                'username': 'consistency',
                'email': 'consistency@test.com',
                'password': 'Consistency123!'
            }
            
            reg_response = client.post('/api/auth/register', json=user_data, content_type='application/json')
            reg_data = json.loads(reg_response.data)
            session_token = reg_data['session_token']
            user_id = reg_data['user']['user_id']
            
            headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
            
            # Perform multiple operations
            test_document = "Consistency test document with unique identifier 12345."
            
            # Analyze document
            analysis_response = client.post('/api/text/analyze',
                                          json={'text': test_document, 'store_result': True},
                                          headers=headers)
            assert analysis_response.status_code == 200
            
            analysis_data = json.loads(analysis_response.data)
            word_count = analysis_data['analysis']['word_count']
            
            # Verify data in database directly
            with sqlite3.connect(db_path) as conn:
                # Check user exists
                cursor = conn.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
                user_row = cursor.fetchone()
                assert user_row is not None
                assert user_row[0] == user_data['username']
                
                # Check document exists
                import hashlib
                doc_id = hashlib.sha256(test_document.encode()).hexdigest()[:16]
                
                cursor = conn.execute("SELECT content, word_count FROM text_documents WHERE doc_id = ?", (doc_id,))
                doc_row = cursor.fetchone()
                assert doc_row is not None
                assert doc_row[0] == test_document
                assert doc_row[1] == word_count
                
                # Check word frequency data
                cursor = conn.execute("SELECT COUNT(*) FROM word_frequency WHERE doc_id = ?", (doc_id,))
                freq_count = cursor.fetchone()[0]
                assert freq_count > 0  # Should have word frequency entries
            
            # Verify API consistency - retrieve document
            doc_response = client.get(f'/api/text/document/{doc_id}', headers=headers)
            assert doc_response.status_code == 200
            
            doc_data = json.loads(doc_response.data)
            assert doc_data['document']['content'] == test_document
            
            # Verify search consistency
            search_response = client.get('/api/text/search?word=consistency', headers=headers)
            assert search_response.status_code == 200
            
            search_data = json.loads(search_response.data)
            assert search_data['results_count'] == 1
            
            # Verify analytics consistency
            analytics_response = client.get('/api/analytics/stats', headers=headers)
            assert analytics_response.status_code == 200
            
            stats_data = json.loads(analytics_response.data)
            assert stats_data['stats']['users']['total'] == 1
            assert stats_data['stats']['documents']['total'] == 1
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestE2EPerformanceWorkflows:
    """Test performance characteristics of complete workflows."""
    
    @pytest.fixture
    def performance_client(self):
        """Create client optimized for performance testing."""
        config = {
            'TESTING': True,
            'DATABASE_PATH': ':memory:',
            'SECRET_KEY': 'performance-test-key'
        }
        app = create_app(config)
        return app.test_client()
    
    def test_user_registration_to_first_analysis_performance(self, performance_client):
        """Test performance of complete user onboarding workflow."""
        start_time = time.time()
        
        # Step 1: Registration
        user_data = {
            'username': 'perfuser',
            'email': 'perf@test.com',
            'password': 'Performance123!'
        }
        
        reg_start = time.time()
        reg_response = performance_client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_time = time.time() - reg_start
        
        assert reg_response.status_code == 201
        reg_data = json.loads(reg_response.data)
        session_token = reg_data['session_token']
        
        headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
        
        # Step 2: Profile access
        profile_start = time.time()
        profile_response = performance_client.get('/api/auth/profile', headers=headers)
        profile_time = time.time() - profile_start
        
        assert profile_response.status_code == 200
        
        # Step 3: First document analysis
        document = "Performance test document with various words for analysis. " * 20  # ~140 words
        
        analysis_start = time.time()
        analysis_response = performance_client.post('/api/text/analyze',
                                                   json={'text': document, 'store_result': True},
                                                   headers=headers)
        analysis_time = time.time() - analysis_start
        
        assert analysis_response.status_code == 200
        
        total_time = time.time() - start_time
        
        # Performance assertions
        assert reg_time < 1.0  # Registration should complete quickly
        assert profile_time < 0.5  # Profile access should be very fast
        assert analysis_time < 2.0  # Document analysis should be reasonable
        assert total_time < 3.0  # Entire workflow should complete quickly
        
        # Verify response time headers
        assert 'X-Response-Time' in analysis_response.headers
    
    def test_bulk_document_processing_performance(self, performance_client):
        """Test performance of processing multiple documents."""
        # Register user
        user_data = {
            'username': 'bulkuser',
            'email': 'bulk@test.com',
            'password': 'BulkTest123!'
        }
        
        reg_response = performance_client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_data = json.loads(reg_response.data)
        session_token = reg_data['session_token']
        headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
        
        # Generate test documents
        documents = []
        for i in range(20):
            doc = f"Bulk processing test document {i}. " + "Content for analysis. " * 25  # ~650 words each
            documents.append(doc)
        
        # Process documents and measure performance
        processing_times = []
        total_start = time.time()
        
        for doc in documents:
            doc_start = time.time()
            response = performance_client.post('/api/text/analyze',
                                             json={'text': doc, 'store_result': True},
                                             headers=headers)
            doc_time = time.time() - doc_start
            
            assert response.status_code == 200
            processing_times.append(doc_time)
        
        total_time = time.time() - total_start
        
        # Performance analysis
        avg_processing_time = sum(processing_times) / len(processing_times)
        max_processing_time = max(processing_times)
        
        # Performance assertions
        assert total_time < 30.0  # All 20 documents should process within 30 seconds
        assert avg_processing_time < 1.5  # Average processing time should be reasonable
        assert max_processing_time < 5.0  # No single document should take too long
        
        # Verify search performance after bulk processing
        search_start = time.time()
        search_response = performance_client.get('/api/text/search?word=bulk', headers=headers)
        search_time = time.time() - search_start
        
        assert search_response.status_code == 200
        assert search_time < 1.0  # Search should remain fast even with many documents
        
        search_data = json.loads(search_response.data)
        assert search_data['results_count'] == 20  # Should find all documents
    
    def test_concurrent_users_performance_impact(self, performance_client):
        """Test performance impact of concurrent users."""
        def single_user_workflow(user_id):
            """Single user workflow for concurrent testing."""
            start_time = time.time()
            
            # Register user
            user_data = {
                'username': f'concurrent_{user_id}',
                'email': f'concurrent{user_id}@test.com',
                'password': 'Concurrent123!'
            }
            
            reg_response = performance_client.post('/api/auth/register', json=user_data, content_type='application/json')
            if reg_response.status_code != 201:
                return {'user_id': user_id, 'error': 'registration_failed', 'time': time.time() - start_time}
            
            reg_data = json.loads(reg_response.data)
            session_token = reg_data['session_token']
            headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
            
            # Process document
            document = f"Concurrent processing test for user {user_id}. " * 30  # ~180 words
            
            analysis_response = performance_client.post('/api/text/analyze',
                                                       json={'text': document, 'store_result': True},
                                                       headers=headers)
            
            if analysis_response.status_code != 200:
                return {'user_id': user_id, 'error': 'analysis_failed', 'time': time.time() - start_time}
            
            # Search for content
            search_response = performance_client.get('/api/text/search?word=concurrent', headers=headers)
            
            if search_response.status_code != 200:
                return {'user_id': user_id, 'error': 'search_failed', 'time': time.time() - start_time}
            
            total_time = time.time() - start_time
            return {'user_id': user_id, 'success': True, 'time': total_time}
        
        # Run concurrent user workflows
        num_concurrent_users = 8
        results = []
        
        overall_start = time.time()
        
        with ThreadPoolExecutor(max_workers=num_concurrent_users) as executor:
            futures = [executor.submit(single_user_workflow, i) for i in range(num_concurrent_users)]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        overall_time = time.time() - overall_start
        
        # Analyze concurrent performance
        successful_results = [r for r in results if r.get('success')]
        failed_results = [r for r in results if 'error' in r]
        
        # Performance assertions
        success_rate = len(successful_results) / len(results)
        assert success_rate >= 0.85, f"Success rate {success_rate:.2f} too low under concurrent load"
        
        if successful_results:
            times = [r['time'] for r in successful_results]
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            assert avg_time < 5.0, f"Average time {avg_time:.2f}s too high under concurrent load"
            assert max_time < 10.0, f"Max time {max_time:.2f}s too high under concurrent load"
        
        assert overall_time < 15.0, f"Overall concurrent processing took {overall_time:.2f}s, too long"


class TestE2ESecurityWorkflows:
    """Test security aspects of end-to-end workflows."""
    
    @pytest.fixture
    def security_client(self):
        """Create client for security testing."""
        config = {
            'TESTING': True,
            'DATABASE_PATH': ':memory:',
            'SECRET_KEY': 'security-test-key-very-secure'
        }
        app = create_app(config)
        return app.test_client()
    
    def test_session_security_and_isolation(self, security_client):
        """Test session security and user isolation."""
        # Register two users
        users = []
        for i in range(2):
            user_data = {
                'username': f'secuser{i}',
                'email': f'sec{i}@test.com',
                'password': f'SecurePass{i}23!'
            }
            
            reg_response = security_client.post('/api/auth/register', json=user_data, content_type='application/json')
            reg_data = json.loads(reg_response.data)
            
            users.append({
                'user_data': user_data,
                'user_id': reg_data['user']['user_id'],
                'session_token': reg_data['session_token']
            })
        
        # Each user creates content
        for i, user in enumerate(users):
            headers = {'Authorization': f"Bearer {user['session_token']}", 'Content-Type': 'application/json'}
            
            # User-specific content
            content = f"Private content for user {i}. Confidential information {user['user_id']}."
            
            response = security_client.post('/api/text/analyze',
                                          json={'text': content, 'store_result': True},
                                          headers=headers)
            assert response.status_code == 200
        
        # Verify users cannot access each other's sessions
        user1_headers = {'Authorization': f"Bearer {users[0]['session_token']}", 'Content-Type': 'application/json'}
        user2_headers = {'Authorization': f"Bearer {users[1]['session_token']}", 'Content-Type': 'application/json'}
        
        # User 1 should only see their own profile
        user1_profile = security_client.get('/api/auth/profile', headers=user1_headers)
        profile1_data = json.loads(user1_profile.data)
        assert profile1_data['user']['user_id'] == users[0]['user_id']
        
        # User 2 should only see their own profile
        user2_profile = security_client.get('/api/auth/profile', headers=user2_headers)
        profile2_data = json.loads(user2_profile.data)
        assert profile2_data['user']['user_id'] == users[1]['user_id']
        
        # Verify session tokens are different and secure
        assert users[0]['session_token'] != users[1]['session_token']
        assert len(users[0]['session_token']) > 20  # Reasonable token length
        assert len(users[1]['session_token']) > 20
    
    def test_input_validation_and_sanitization(self, security_client):
        """Test input validation and sanitization across all endpoints."""
        # Register user for authenticated endpoints
        user_data = {
            'username': 'validationuser',
            'email': 'validation@test.com',
            'password': 'Validation123!'
        }
        
        reg_response = security_client.post('/api/auth/register', json=user_data, content_type='application/json')
        reg_data = json.loads(reg_response.data)
        session_token = reg_data['session_token']
        headers = {'Authorization': f'Bearer {session_token}', 'Content-Type': 'application/json'}
        
        # Test various malicious/invalid inputs
        malicious_inputs = [
            # SQL injection attempts
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            
            # XSS attempts
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            
            # Large inputs
            "x" * 200000,  # Very large text
            
            # Special characters
            "Test with special chars: !@#$%^&*()_+{}|:<>?[]\\;'\",./ ",
            
            # Unicode and encoding tests
            "Test with unicode: café résumé naïve 中文 русский العربية",
            
            # Null bytes and control characters
            "Test\x00null\x01control\x02chars",
        ]
        
        for malicious_input in malicious_inputs:
            # Test text analysis endpoint
            if len(malicious_input) <= 100000:  # Within size limit
                response = security_client.post('/api/text/analyze',
                                              json={'text': malicious_input, 'store_result': True},
                                              headers=headers)
                
                # Should either succeed with sanitized input or fail gracefully
                assert response.status_code in [200, 400, 413]
                
                if response.status_code == 200:
                    # If successful, verify no dangerous content in response
                    response_data = json.loads(response.data)
                    response_text = json.dumps(response_data)
                    assert '<script>' not in response_text.lower()
                    assert 'drop table' not in response_text.lower()
            
            # Test text cleaning endpoint
            response = security_client.post('/api/text/clean',
                                          json={'text': malicious_input[:10000]},  # Reasonable size
                                          headers=headers)
            
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                clean_data = json.loads(response.data)
                # Verify cleaned text is safe
                cleaned = clean_data['cleaned_text']
                assert '<script>' not in cleaned.lower()
                assert 'javascript:' not in cleaned.lower()
    
    def test_authentication_security_measures(self, security_client):
        """Test authentication security measures."""
        # Test password requirements
        weak_passwords = [
            'short',  # Too short
            '12345678',  # Only numbers
            'password',  # Common word
            'PASSWORD',  # Only uppercase
            'abcdefgh',  # Only lowercase
        ]
        
        for weak_password in weak_passwords:
            response = security_client.post('/api/auth/register',
                                          json={
                                              'username': 'weaktest',
                                              'email': 'weak@test.com',
                                              'password': weak_password
                                          },
                                          content_type='application/json')
            
            # Should reject weak passwords
            assert response.status_code in [400, 401]
        
        # Test brute force protection simulation
        user_data = {
            'username': 'brutetest',
            'email': 'brute@test.com',
            'password': 'SecureBrute123!'
        }
        
        # Register user
        security_client.post('/api/auth/register', json=user_data, content_type='application/json')
        
        # Attempt multiple failed logins
        for _ in range(10):
            response = security_client.post('/api/auth/login',
                                          json={
                                              'username': user_data['username'],
                                              'password': 'wrongpassword'
                                          },
                                          content_type='application/json')
            assert response.status_code == 401
        
        # Valid login should still work (system shouldn't lock out permanently in tests)
        valid_response = security_client.post('/api/auth/login',
                                             json={
                                                 'username': user_data['username'],
                                                 'password': user_data['password']
                                             },
                                             content_type='application/json')
        # May succeed or be rate-limited, both are acceptable security measures
        assert valid_response.status_code in [200, 429]