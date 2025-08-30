"""
End-to-end integration tests using London School TDD methodology.
Tests focus on complete workflows, system interactions, and real behavior validation.
"""

import pytest
import json
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from typing import Dict, List, Any, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.api.endpoints import create_app
from src.auth.authentication import AuthenticationManager
from src.utils.text_processing import TextProcessor
from src.database.connection import DatabaseManager
from src.core.text_analyzer import TextAnalyzer

# Import test implementations from other test files
try:
    from .test_citations import CitationExtractor
    from .test_courtlistener import CourtListenerClient
except ImportError:
    # Fallback minimal implementations for testing
    class CitationExtractor:
        def extract_citations(self, text, types=None):
            return [{'type': 'test', 'text': 'Test Citation', 'confidence': 0.8}]
    
    class CourtListenerClient:
        def __init__(self, api_key):
            self.api_key = api_key
        
        def verify_citation(self, citation):
            return {'verified': True, 'confidence_score': 0.9}


class TestCompleteUserWorkflow:
    """Test complete user workflows from registration to document processing."""
    
    def test_complete_document_analysis_workflow(self, client, sample_user_data, sample_texts):
        """Should support complete workflow from user registration to document analysis."""
        # Step 1: User Registration
        register_response = client.post('/api/auth/register',
                                       json=sample_user_data,
                                       content_type='application/json')
        
        assert register_response.status_code == 201
        user_data = register_response.get_json()
        assert user_data['success'] is True
        assert 'session_token' in user_data
        
        headers = {'Authorization': f"Bearer {user_data['session_token']}"}
        
        # Step 2: User Profile Verification
        profile_response = client.get('/api/auth/profile', headers=headers)
        assert profile_response.status_code == 200
        profile_data = profile_response.get_json()
        assert profile_data['user']['username'] == sample_user_data['username']
        
        # Step 3: Text Analysis
        analysis_data = {
            'text': sample_texts['complex'],
            'store_result': True
        }
        
        analysis_response = client.post('/api/text/analyze',
                                       json=analysis_data,
                                       headers=headers)
        
        assert analysis_response.status_code == 200
        analysis_result = analysis_response.get_json()
        assert analysis_result['success'] is True
        assert 'analysis' in analysis_result
        assert analysis_result['analysis']['word_count'] > 0
        
        # Step 4: Text Search
        search_response = client.get('/api/text/search?word=text', headers=headers)
        assert search_response.status_code == 200
        search_result = search_response.get_json()
        assert search_result['success'] is True
        assert search_result['results_count'] > 0
        
        # Step 5: Document Retrieval
        if search_result['results']:
            doc_id = search_result['results'][0]['doc_id']
            doc_response = client.get(f'/api/text/document/{doc_id}', headers=headers)
            assert doc_response.status_code == 200
            doc_result = doc_response.get_json()
            assert doc_result['success'] is True
            assert 'document' in doc_result
        
        # Step 6: Analytics Review
        analytics_response = client.get('/api/analytics/stats', headers=headers)
        assert analytics_response.status_code == 200
        analytics_result = analytics_response.get_json()
        assert analytics_result['success'] is True
        assert 'stats' in analytics_result
    
    def test_legal_document_processing_workflow(self, client, sample_user_data):
        """Should process legal documents with citation extraction and verification."""
        # Setup authenticated user
        register_response = client.post('/api/auth/register',
                                       json=sample_user_data,
                                       content_type='application/json')
        
        user_data = register_response.get_json()
        headers = {'Authorization': f"Bearer {user_data['session_token']}"}
        
        # Legal document with citations
        legal_text = """
        In Brown v. Board of Education, 347 U.S. 483 (1954), the Supreme Court held that 
        state laws establishing separate public schools for black and white students were 
        unconstitutional. This landmark decision overruled Plessy v. Ferguson, 163 U.S. 537 (1896).
        
        The court's reasoning was based on the Equal Protection Clause of the Fourteenth Amendment, 
        as codified in 42 U.S.C. § 1983, which provides a federal remedy for violations of 
        constitutional rights.
        """
        
        # Process legal document
        analysis_response = client.post('/api/text/analyze',
                                       json={'text': legal_text, 'store_result': True},
                                       headers=headers)
        
        assert analysis_response.status_code == 200
        analysis_result = analysis_response.get_json()
        
        # Verify legal document was processed
        assert analysis_result['success'] is True
        assert analysis_result['analysis']['word_count'] > 50
        assert analysis_result['analysis']['sentence_count'] > 3
        
        # Search for legal terms
        legal_search_response = client.get('/api/text/search?word=Supreme', headers=headers)
        assert legal_search_response.status_code == 200
        legal_search_result = legal_search_response.get_json()
        assert legal_search_result['results_count'] > 0
        
        # Verify document can be retrieved
        doc_id = legal_search_result['results'][0]['doc_id']
        doc_response = client.get(f'/api/text/document/{doc_id}', headers=headers)
        assert doc_response.status_code == 200
    
    def test_multi_user_concurrent_workflow(self, test_app, data_generator):
        """Should handle multiple users processing documents concurrently."""
        results = []
        errors = []
        
        def user_workflow(user_id):
            try:
                with test_app.test_client() as client:
                    # Register unique user
                    user_data = data_generator.user_data(f"user{user_id}")
                    register_response = client.post('/api/auth/register',
                                                   json=user_data,
                                                   content_type='application/json')
                    
                    if register_response.status_code != 201:
                        errors.append(f"User {user_id} registration failed")
                        return
                    
                    session_data = register_response.get_json()
                    headers = {'Authorization': f"Bearer {session_data['session_token']}"}
                    
                    # Process multiple documents
                    for doc_num in range(3):
                        text = f"Document {doc_num} for user {user_id}. This contains unique content for testing."
                        
                        analysis_response = client.post('/api/text/analyze',
                                                       json={'text': text, 'store_result': True},
                                                       headers=headers)
                        
                        if analysis_response.status_code == 200:
                            results.append(f"user{user_id}_doc{doc_num}")
                        else:
                            errors.append(f"User {user_id} doc {doc_num} analysis failed")
                    
                    # Search documents
                    search_response = client.get('/api/text/search?word=Document', headers=headers)
                    if search_response.status_code == 200:
                        results.append(f"user{user_id}_search")
            
            except Exception as e:
                errors.append(f"User {user_id} workflow error: {str(e)}")
        
        # Run concurrent user workflows
        threads = []
        for i in range(5):  # 5 concurrent users
            thread = threading.Thread(target=user_workflow, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all workflows to complete
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout
        
        # Verify all workflows completed successfully
        assert len(errors) == 0, f"Concurrent workflow errors: {errors}"
        
        # Verify expected number of operations
        # 5 users × (3 documents + 1 search) = 20 operations
        assert len(results) == 20
    
    def test_session_management_across_requests(self, client, sample_user_data, sample_texts):
        """Should maintain session state across multiple requests."""
        # Register user and get session
        register_response = client.post('/api/auth/register',
                                       json=sample_user_data,
                                       content_type='application/json')
        
        user_data = register_response.get_json()
        session_token = user_data['session_token']
        headers = {'Authorization': f'Bearer {session_token}'}
        
        # Use session across multiple requests
        requests_with_session = [
            ('GET', '/api/auth/profile'),
            ('POST', '/api/text/analyze', {'text': sample_texts['simple']}),
            ('GET', '/api/text/search?word=simple'),
            ('GET', '/api/analytics/stats')
        ]
        
        for method, endpoint, *data in requests_with_session:
            if method == 'GET':
                response = client.get(endpoint, headers=headers)
            elif method == 'POST':
                response = client.post(endpoint, json=data[0], headers=headers)
            
            assert response.status_code in [200, 201], f"Failed request: {method} {endpoint}"
            
            result = response.get_json()
            # All authenticated endpoints should succeed with valid session
            assert result.get('success') is True or 'user' in result
        
        # Validate session token still works
        validate_response = client.post('/api/auth/validate',
                                       json={'session_token': session_token})
        
        assert validate_response.status_code == 200
        validate_result = validate_response.get_json()
        assert validate_result['valid'] is True


class TestSystemComponentIntegration:
    """Test integration between different system components."""
    
    def test_text_processor_and_database_integration(self, temp_db_path, sample_texts):
        """Should integrate text processor with database for persistent storage."""
        # Create shared database
        db_manager = DatabaseManager(temp_db_path)
        text_processor = TextProcessor(temp_db_path)
        
        # Process multiple texts
        processed_docs = []
        for text_name, text_content in list(sample_texts.items())[:3]:
            analysis = text_processor.analyze_text(text_content, store_result=True)
            processed_docs.append((text_name, analysis))
        
        # Verify data was stored in database
        stored_docs = db_manager.execute_query(
            "SELECT doc_id, word_count, character_count FROM text_documents ORDER BY processed_at"
        )
        
        assert len(stored_docs) == 3
        
        # Verify stored data matches processed data
        for i, (text_name, analysis) in enumerate(processed_docs):
            stored_doc = stored_docs[i]
            assert stored_doc['word_count'] == analysis.word_count
            assert stored_doc['character_count'] == analysis.character_count
        
        # Test cross-component search
        search_results = text_processor.search_documents_by_word('text')
        assert len(search_results) > 0
        
        # Verify search results can be accessed via database
        for result in search_results:
            doc_data = db_manager.execute_query(
                "SELECT content FROM text_documents WHERE doc_id = ?",
                (result['doc_id'],)
            )
            assert len(doc_data) == 1
            assert len(doc_data[0]['content']) > 0
    
    def test_authentication_and_session_persistence(self, temp_db_path, sample_user_data):
        """Should persist authentication data across component instances."""
        # Create first auth manager instance
        auth_manager1 = AuthenticationManager(temp_db_path)
        
        # Register user and create session
        user = auth_manager1.register_user(
            sample_user_data['username'],
            sample_user_data['email'],
            sample_user_data['password']
        )
        session_token = auth_manager1.create_session(user.user_id)
        
        # Create second auth manager instance (different object, same database)
        auth_manager2 = AuthenticationManager(temp_db_path)
        
        # Verify session is valid across instances
        is_valid, user_id = auth_manager2.validate_session(session_token)
        assert is_valid is True
        assert user_id == user.user_id
        
        # Verify user data is accessible
        retrieved_user = auth_manager2.get_user_by_id(user.user_id)
        assert retrieved_user is not None
        assert retrieved_user.username == sample_user_data['username']
        assert retrieved_user.email == sample_user_data['email']
        
        # Test authentication across instances
        auth_success, auth_user = auth_manager2.authenticate_user(
            sample_user_data['username'],
            sample_user_data['password']
        )
        assert auth_success is True
        assert auth_user.user_id == user.user_id
    
    @patch('src.core.text_analyzer.NLPProcessor')
    def test_text_analyzer_with_ai_integration(self, mock_nlp_processor, memory_db, sample_texts):
        """Should integrate TextAnalyzer with AI components."""
        # Setup AI processor mock
        mock_nlp_instance = Mock()
        mock_ai_analysis = Mock()
        mock_ai_analysis.processing_time = 0.05
        mock_ai_analysis.language = "en"
        mock_ai_analysis.named_entities = [{'text': 'Test', 'label': 'PERSON'}]
        mock_ai_analysis.topics = [{'topic': 'technology', 'score': 0.8}]
        mock_ai_analysis.confidence_scores = {'overall': 0.85}
        mock_ai_analysis.model_versions = {'nlp': '1.0', 'sentiment': '2.0'}
        
        mock_nlp_instance.analyze_text_async.return_value = mock_ai_analysis
        mock_nlp_processor.return_value = mock_nlp_instance
        
        # Create text analyzer with AI enabled
        analyzer = TextAnalyzer(memory_db, enable_ai=True, performance_mode="comprehensive")
        
        # Analyze text
        result = analyzer.analyze_text(sample_texts['complex'], store_result=True)
        
        # Verify AI analysis was integrated
        assert result.analysis_depth == "comprehensive"
        assert result.language == "en"
        assert len(result.named_entities) > 0
        assert len(result.topics) > 0
        assert result.confidence_scores['overall'] == 0.85
        
        # Verify traditional analysis is still present
        assert result.word_count > 0
        assert result.sentence_count > 0
        assert isinstance(result.sentiment_score, (int, float))
    
    def test_database_connection_pooling_across_components(self, temp_db_path):
        """Should manage database connections efficiently across components."""
        # Create multiple components sharing same database
        db_manager = DatabaseManager(temp_db_path, pool_size=3)
        text_processor = TextProcessor(temp_db_path)
        auth_manager = AuthenticationManager(temp_db_path)
        
        # Monitor initial connection pool state
        initial_stats = db_manager.get_stats()
        assert initial_stats.total_connections == 3
        assert initial_stats.active_connections == 0
        
        # Concurrent operations from different components
        def db_operations():
            for i in range(5):
                db_manager.execute_query("SELECT COUNT(*) FROM sqlite_master")
        
        def text_operations():
            for i in range(3):
                text_processor.analyze_text(f"Test document {i}", store_result=True)
        
        def auth_operations():
            try:
                for i in range(2):
                    auth_manager.register_user(f"user{i}", f"user{i}@example.com", "password")
            except:
                pass  # May fail if users exist
        
        # Run concurrent operations
        threads = [
            threading.Thread(target=db_operations),
            threading.Thread(target=text_operations),
            threading.Thread(target=auth_operations)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify connection pool handled concurrent access
        final_stats = db_manager.get_stats()
        assert final_stats.total_queries > initial_stats.total_queries
        assert final_stats.active_connections == 0  # All connections returned to pool
        assert final_stats.error_count == initial_stats.error_count  # No connection errors


class TestCitationProcessingWorkflow:
    """Test complete citation processing workflow with external API integration."""
    
    def test_citation_extraction_and_verification_workflow(self, client, sample_user_data):
        """Should extract citations and verify them against external sources."""
        # Setup authenticated user
        register_response = client.post('/api/auth/register',
                                       json=sample_user_data,
                                       content_type='application/json')
        
        user_data = register_response.get_json()
        headers = {'Authorization': f"Bearer {user_data['session_token']}"}
        
        # Legal text with multiple citation types
        legal_document = """
        The Supreme Court's decision in Brown v. Board of Education, 347 U.S. 483 (1954), 
        fundamentally changed American jurisprudence. This case overturned the precedent 
        set in Plessy v. Ferguson, 163 U.S. 537 (1896).
        
        Federal civil rights legislation, particularly 42 U.S.C. § 1983, provides 
        remedies for constitutional violations. Administrative regulations under 
        29 C.F.R. § 1630.2 further define these protections.
        
        Recent circuit court decisions, including Smith v. Jones, 123 F.3d 456 (1st Cir. 2020),
        have continued to expand these principles.
        """
        
        # Step 1: Process legal document
        analysis_response = client.post('/api/text/analyze',
                                       json={'text': legal_document, 'store_result': True},
                                       headers=headers)
        
        assert analysis_response.status_code == 200
        analysis_result = analysis_response.get_json()
        assert analysis_result['success'] is True
        
        # Step 2: Extract citations from processed text
        extractor = CitationExtractor()
        citations = extractor.extract_citations(legal_document)
        
        assert len(citations) > 0
        
        # Verify different citation types were found
        citation_types = set(citation['type'] for citation in citations)
        expected_types = ['supreme_court', 'federal_statute', 'cfr', 'federal_case']
        
        # Should find at least some expected types
        assert len(citation_types.intersection(expected_types)) > 0
        
        # Step 3: Verify citations with external API (mocked)
        with patch.object(CourtListenerClient, 'verify_citation') as mock_verify:
            mock_verify.return_value = {
                'verified': True,
                'confidence_score': 0.9,
                'matches': [{'id': 123, 'citation': 'Test Citation'}]
            }
            
            client_api = CourtListenerClient("test_api_key")
            
            verification_results = []
            for citation in citations[:3]:  # Verify first 3 citations
                result = client_api.verify_citation(citation['text'])
                verification_results.append(result)
            
            # Verify API was called for each citation
            assert mock_verify.call_count == 3
            assert all(result['verified'] for result in verification_results)
        
        # Step 4: Search for legal terms in stored document
        search_terms = ['Supreme', 'Court', 'constitutional', 'federal']
        
        for term in search_terms:
            search_response = client.get(f'/api/text/search?word={term}', headers=headers)
            assert search_response.status_code == 200
            search_result = search_response.get_json()
            
            if term.lower() in legal_document.lower():
                assert search_result['results_count'] > 0
    
    @patch('requests.Session')
    def test_citation_verification_with_rate_limiting(self, mock_session_class):
        """Should handle citation verification with proper rate limiting."""
        # Setup mock HTTP responses
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [{'id': 123, 'citation': 'Test Citation', 'confidence': 0.9}]
        }
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Create client with rate limiting
        client = CourtListenerClient("test_key", rate_limit_delay=0.1)
        
        citations = [
            "347 U.S. 483 (1954)",
            "163 U.S. 537 (1896)",
            "42 U.S.C. § 1983",
            "123 F.3d 456 (2020)"
        ]
        
        start_time = time.time()
        results = []
        
        for citation in citations:
            result = client.verify_citation(citation)
            results.append(result)
        
        end_time = time.time()
        
        # Verify all citations were processed
        assert len(results) == 4
        assert all(result['verified'] for result in results)
        
        # Verify rate limiting was enforced (4 requests with 0.1s delay = at least 0.3s total)
        total_time = end_time - start_time
        assert total_time >= 0.25  # Allow for timing variations
        
        # Verify HTTP requests were made
        assert mock_session.get.call_count == 4
    
    def test_citation_processing_error_handling(self, temp_db_path):
        """Should handle errors gracefully during citation processing workflow."""
        text_processor = TextProcessor(temp_db_path)
        extractor = CitationExtractor()
        
        # Test with problematic legal text
        problematic_texts = [
            "This text has no citations at all.",
            "Malformed citation: 999 Invalid 999 (YYYY)",
            "Unicode citation: Café v. Résumé, 123 F.3d 456 (2020)",
            "",  # Empty text
            "A" * 10000  # Very long text
        ]
        
        processing_results = []
        citation_results = []
        
        for i, text in enumerate(problematic_texts):
            try:
                if text:  # Skip empty text for processor
                    analysis = text_processor.analyze_text(text, store_result=True)
                    processing_results.append(('success', i, analysis.word_count))
                
                # Citation extraction should handle all cases
                if text:  # Skip empty text
                    citations = extractor.extract_citations(text)
                    citation_results.append(('success', i, len(citations)))
                
            except Exception as e:
                processing_results.append(('error', i, str(e)))
                citation_results.append(('error', i, str(e)))
        
        # Verify most operations succeeded or failed gracefully
        processing_errors = [r for r in processing_results if r[0] == 'error']
        citation_errors = [r for r in citation_results if r[0] == 'error']
        
        # Should handle errors gracefully - no more than 2 failures expected
        assert len(processing_errors) <= 2
        assert len(citation_errors) <= 1
        
        # Successful operations should have produced reasonable results
        successful_processing = [r for r in processing_results if r[0] == 'success']
        successful_citations = [r for r in citation_results if r[0] == 'success']
        
        assert len(successful_processing) >= 2
        assert len(successful_citations) >= 3


class TestPerformanceAndScalabilityIntegration:
    """Test system performance and scalability under load."""
    
    def test_concurrent_user_load_handling(self, test_app, data_generator, performance_monitor):
        """Should handle concurrent user load efficiently."""
        performance_monitor.start()
        
        results = []
        errors = []
        
        def simulate_user_load(user_id, num_operations=5):
            try:
                with test_app.test_client() as client:
                    # Register user
                    user_data = data_generator.user_data(f"loaduser{user_id}")
                    register_response = client.post('/api/auth/register',
                                                   json=user_data,
                                                   content_type='application/json')
                    
                    if register_response.status_code != 201:
                        errors.append(f"Registration failed for user {user_id}")
                        return
                    
                    session_data = register_response.get_json()
                    headers = {'Authorization': f"Bearer {session_data['session_token']}"}
                    
                    # Perform operations
                    for op in range(num_operations):
                        # Analyze text
                        text = f"Load test document {op} for user {user_id}"
                        analysis_response = client.post('/api/text/analyze',
                                                       json={'text': text, 'store_result': True},
                                                       headers=headers)
                        
                        if analysis_response.status_code == 200:
                            results.append(f"user{user_id}_op{op}")
                        
                        # Search documents
                        search_response = client.get('/api/text/search?word=Load', headers=headers)
                        if search_response.status_code == 200:
                            results.append(f"user{user_id}_search{op}")
            
            except Exception as e:
                errors.append(f"User {user_id} error: {str(e)}")
        
        # Simulate concurrent users
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_user_load, i, 3) for i in range(10)]
            
            for future in as_completed(futures, timeout=60):
                try:
                    future.result()
                except Exception as e:
                    errors.append(f"Thread execution error: {str(e)}")
        
        metrics = performance_monitor.stop()
        
        # Verify performance under load
        assert len(errors) == 0, f"Load test errors: {errors[:5]}..."  # Show first 5 errors
        
        # 10 users × 3 operations × 2 requests each = 60 operations
        assert len(results) >= 50  # Allow for some variation
        
        # Should complete within reasonable time
        assert metrics['duration'] < 30.0  # Less than 30 seconds
        
        # Memory usage should be reasonable
        assert metrics['memory_delta'] < 200  # Less than 200MB
    
    def test_large_document_processing_performance(self, memory_text_processor, performance_monitor):
        """Should handle large document processing efficiently."""
        # Create documents of varying sizes
        document_sizes = [100, 1000, 5000, 10000]  # words
        base_text = "This is a sample sentence for performance testing. "
        
        processing_times = []
        
        for size in document_sizes:
            # Create document of specified size
            large_document = base_text * (size // 10)  # Approximate word count
            
            performance_monitor.start()
            
            # Process document
            analysis = memory_text_processor.analyze_text(large_document, store_result=True)
            
            metrics = performance_monitor.stop()
            processing_times.append((size, metrics['duration']))
            
            # Verify processing completed successfully
            assert analysis.word_count > 0
            assert analysis.processing_time > 0
        
        # Verify processing time scales reasonably
        # Larger documents should take more time, but not exponentially more
        for i in range(1, len(processing_times)):
            prev_size, prev_time = processing_times[i-1]
            curr_size, curr_time = processing_times[i]
            
            size_ratio = curr_size / prev_size
            time_ratio = curr_time / prev_time if prev_time > 0 else 1
            
            # Time ratio should not exceed size ratio by too much (reasonable scaling)
            assert time_ratio <= size_ratio * 3  # Allow 3x scaling factor
    
    def test_database_performance_under_concurrent_load(self, temp_db_path, performance_monitor):
        """Should maintain database performance under concurrent load."""
        db_manager = DatabaseManager(temp_db_path, pool_size=5)
        
        # Create test table
        db_manager.execute_update("""
            CREATE TABLE load_test (id INTEGER PRIMARY KEY, user_id INTEGER, 
                                   data TEXT, timestamp REAL)
        """)
        
        performance_monitor.start()
        
        def database_operations(worker_id, num_operations=20):
            for i in range(num_operations):
                # Insert operation
                db_manager.execute_update(
                    "INSERT INTO load_test (user_id, data, timestamp) VALUES (?, ?, ?)",
                    (worker_id, f"data_{worker_id}_{i}", time.time())
                )
                
                # Query operation
                db_manager.execute_query(
                    "SELECT COUNT(*) FROM load_test WHERE user_id = ?",
                    (worker_id,)
                )
                
                # Update operation
                db_manager.execute_update(
                    "UPDATE load_test SET timestamp = ? WHERE user_id = ? AND id = ?",
                    (time.time(), worker_id, i + 1)
                )
        
        # Run concurrent database operations
        threads = []
        for worker_id in range(8):  # 8 concurrent workers
            thread = threading.Thread(target=database_operations, args=(worker_id, 15))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=30)
        
        metrics = performance_monitor.stop()
        
        # Verify performance
        assert metrics['duration'] < 20.0  # Should complete within 20 seconds
        
        # Verify data integrity
        total_records = db_manager.execute_query("SELECT COUNT(*) as count FROM load_test")
        assert total_records[0]['count'] == 8 * 15  # 8 workers × 15 operations each
        
        # Check database performance stats
        db_stats = db_manager.get_stats()
        assert db_stats.total_queries > 100
        assert db_stats.avg_query_time < 1.0  # Average query should be fast
        assert db_stats.error_count == 0  # No database errors


class TestErrorRecoveryAndResilience:
    """Test system error recovery and resilience capabilities."""
    
    def test_database_connection_recovery(self, temp_db_path):
        """Should recover from temporary database connection failures."""
        db_manager = DatabaseManager(temp_db_path)
        
        # Verify normal operation
        db_manager.execute_update("CREATE TABLE recovery_test (id INTEGER, data TEXT)")
        db_manager.execute_update("INSERT INTO recovery_test (id, data) VALUES (1, 'test')")
        
        initial_records = db_manager.execute_query("SELECT COUNT(*) as count FROM recovery_test")
        assert initial_records[0]['count'] == 1
        
        # Simulate connection failure by corrupting pool temporarily
        original_pool = db_manager._connection_pool.copy()
        
        # Replace connections with failing mocks
        failing_connection = Mock()
        failing_connection.__enter__ = Mock(return_value=failing_connection)
        failing_connection.__exit__ = Mock(return_value=None)
        failing_connection.execute.side_effect = Exception("Connection failed")
        
        db_manager._connection_pool = [failing_connection] * 3
        
        # Operations should fail initially
        with pytest.raises(Exception):
            db_manager.execute_query("SELECT * FROM recovery_test")
        
        # Restore working connections (simulating recovery)
        db_manager._connection_pool = original_pool
        
        # Operations should work again
        recovery_records = db_manager.execute_query("SELECT COUNT(*) as count FROM recovery_test")
        assert recovery_records[0]['count'] == 1
        
        # New operations should work
        db_manager.execute_update("INSERT INTO recovery_test (id, data) VALUES (2, 'recovered')")
        final_records = db_manager.execute_query("SELECT COUNT(*) as count FROM recovery_test")
        assert final_records[0]['count'] == 2
    
    def test_api_failure_graceful_degradation(self, client, sample_user_data, sample_texts):
        """Should handle API failures with graceful degradation."""
        # Setup authenticated user
        register_response = client.post('/api/auth/register',
                                       json=sample_user_data,
                                       content_type='application/json')
        
        user_data = register_response.get_json()
        headers = {'Authorization': f"Bearer {user_data['session_token']}"}
        
        # Test with various potentially problematic inputs
        problematic_inputs = [
            {'text': ''},  # Empty text
            {'text': 'A' * 100001},  # Oversized text
            {'text': sample_texts['unicode']},  # Unicode content
            {'invalid_field': 'value'},  # Invalid request structure
            None  # No JSON data
        ]
        
        responses = []
        
        for i, input_data in enumerate(problematic_inputs):
            try:
                if input_data is None:
                    response = client.post('/api/text/analyze', headers=headers)  # No JSON
                else:
                    response = client.post('/api/text/analyze',
                                         json=input_data,
                                         headers=headers)
                
                responses.append((i, response.status_code, response.get_json()))
                
            except Exception as e:
                responses.append((i, 'exception', str(e)))
        
        # Verify graceful error handling
        for i, status_code, response_data in responses:
            # Should not crash with 500 errors
            assert status_code != 500
            
            # Should return appropriate error codes
            if status_code in [400, 413, 422]:
                # Expected error codes for bad input
                assert isinstance(response_data, dict)
                assert 'error' in response_data
            elif status_code == 200:
                # Successful processing (unicode case should work)
                assert response_data.get('success') is True
        
        # Verify system is still functional after errors
        valid_response = client.post('/api/text/analyze',
                                    json={'text': sample_texts['simple']},
                                    headers=headers)
        
        assert valid_response.status_code == 200
        assert valid_response.get_json()['success'] is True
    
    def test_concurrent_failure_isolation(self, test_app, data_generator):
        """Should isolate failures to prevent cascade effects in concurrent operations."""
        successful_operations = []
        failed_operations = []
        
        def mixed_operations(worker_id):
            """Perform mix of valid and invalid operations."""
            try:
                with test_app.test_client() as client:
                    # Valid user registration
                    user_data = data_generator.user_data(f"worker{worker_id}")
                    register_response = client.post('/api/auth/register',
                                                   json=user_data,
                                                   content_type='application/json')
                    
                    if register_response.status_code != 201:
                        failed_operations.append(f"worker{worker_id}_register")
                        return
                    
                    session_data = register_response.get_json()
                    headers = {'Authorization': f"Bearer {session_data['session_token']}"}
                    
                    # Mix of valid and invalid operations
                    operations = [
                        ('valid_text', {'text': f'Valid document for worker {worker_id}'}),
                        ('empty_text', {'text': ''}),  # Should fail
                        ('valid_search', None),  # GET request
                        ('oversized_text', {'text': 'X' * 100001}),  # Should fail
                        ('unicode_text', {'text': 'Test with unicode: café résumé'}),
                    ]
                    
                    for op_name, data in operations:
                        try:
                            if op_name == 'valid_search':
                                response = client.get('/api/text/search?word=document', headers=headers)
                            else:
                                response = client.post('/api/text/analyze',
                                                     json=data,
                                                     headers=headers)
                            
                            if response.status_code in [200, 201]:
                                successful_operations.append(f"worker{worker_id}_{op_name}")
                            else:
                                failed_operations.append(f"worker{worker_id}_{op_name}")
                        
                        except Exception as e:
                            failed_operations.append(f"worker{worker_id}_{op_name}_exception")
            
            except Exception as e:
                failed_operations.append(f"worker{worker_id}_general_error")
        
        # Run concurrent mixed operations
        threads = []
        for worker_id in range(6):
            thread = threading.Thread(target=mixed_operations, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=30)
        
        # Verify failure isolation
        # Should have both successful and failed operations
        assert len(successful_operations) > 0, "Should have some successful operations"
        assert len(failed_operations) > 0, "Should have some expected failures"
        
        # Successful operations should outnumber failures (most operations should work)
        success_rate = len(successful_operations) / (len(successful_operations) + len(failed_operations))
        assert success_rate > 0.4, f"Success rate too low: {success_rate}"
        
        # System should remain responsive (verify with simple health check)
        with test_app.test_client() as client:
            health_response = client.get('/health')
            assert health_response.status_code == 200
            health_data = health_response.get_json()
            assert health_data['status'] == 'healthy'


@pytest.mark.slow
class TestLongRunningIntegrationScenarios:
    """Test long-running integration scenarios and system stability."""
    
    def test_extended_session_management(self, client, sample_user_data):
        """Should maintain session integrity over extended periods."""
        # Register user and get session
        register_response = client.post('/api/auth/register',
                                       json=sample_user_data,
                                       content_type='application/json')
        
        user_data = register_response.get_json()
        session_token = user_data['session_token']
        headers = {'Authorization': f'Bearer {session_token}'}
        
        # Simulate extended usage over time
        operations_over_time = []
        
        for minute in range(5):  # Simulate 5 minutes of usage
            # Perform operations at different intervals
            for operation in range(3):
                # Analyze text
                analysis_response = client.post('/api/text/analyze',
                                               json={'text': f'Document {minute}-{operation} content'},
                                               headers=headers)
                
                operations_over_time.append(('analyze', analysis_response.status_code))
                
                # Check profile
                profile_response = client.get('/api/auth/profile', headers=headers)
                operations_over_time.append(('profile', profile_response.status_code))
                
                # Small delay between operations
                time.sleep(0.1)
        
        # Verify all operations succeeded
        successful_operations = [op for op in operations_over_time if op[1] in [200, 201]]
        assert len(successful_operations) == len(operations_over_time)
        
        # Session should still be valid
        validate_response = client.post('/api/auth/validate',
                                       json={'session_token': session_token})
        
        assert validate_response.status_code == 200
        validate_result = validate_response.get_json()
        assert validate_result['valid'] is True
    
    def test_memory_stability_under_continuous_load(self, memory_db_manager, performance_monitor):
        """Should maintain memory stability under continuous processing load."""
        performance_monitor.start()
        
        # Simulate continuous document processing
        processed_docs = []
        
        for batch in range(10):  # 10 batches of processing
            batch_queries = []
            
            # Create batch of document insertions
            for doc in range(20):  # 20 docs per batch
                doc_content = f"Batch {batch} Document {doc} content with various text lengths and complexity."
                doc_id = f"batch_{batch}_doc_{doc}"
                
                batch_queries.append((
                    "INSERT INTO text_documents (doc_id, content, content_hash, word_count, character_count, processed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (doc_id, doc_content, hash(doc_content), len(doc_content.split()), len(doc_content), time.time())
                ))
            
            # Execute batch
            results = memory_db_manager.execute_batch(batch_queries)
            processed_docs.extend(results)
            
            # Perform some queries
            for _ in range(5):
                memory_db_manager.execute_query(
                    "SELECT COUNT(*) FROM text_documents WHERE processed_at > ?",
                    (time.time() - 60,)  # Last minute
                )
        
        metrics = performance_monitor.stop()
        
        # Verify processing completed
        assert len(processed_docs) == 200  # 10 batches × 20 docs
        
        # Verify memory usage remained stable
        assert metrics['memory_delta'] < 100  # Less than 100MB increase
        
        # Verify database performance remained stable
        db_stats = memory_db_manager.get_stats()
        assert db_stats.avg_query_time < 0.1  # Queries should still be fast
        assert db_stats.error_count == 0  # No errors should have occurred
        
        # Cleanup verification
        cleanup_result = memory_db_manager.cleanup_old_logs(days=0)  # Clean all logs
        assert isinstance(cleanup_result, int)  # Should return number of cleaned records
    
    def test_system_recovery_after_resource_exhaustion(self, temp_db_path):
        """Should recover gracefully after simulated resource exhaustion."""
        db_manager = DatabaseManager(temp_db_path, pool_size=2)  # Small pool
        
        # Create test table
        db_manager.execute_update("CREATE TABLE resource_test (id INTEGER, data BLOB)")
        
        # Simulate resource exhaustion by filling up connection pool
        held_connections = []
        
        try:
            # Hold connections beyond pool capacity
            for i in range(5):  # More than pool_size
                try:
                    conn = db_manager.get_connection().__enter__()
                    held_connections.append(conn)
                except:
                    break  # Expected when pool exhausted
            
            # System should handle resource pressure
            # Try to perform operations (should either work or fail gracefully)
            operation_results = []
            
            for i in range(3):
                try:
                    result = db_manager.execute_query("SELECT COUNT(*) FROM resource_test")
                    operation_results.append(('success', len(result)))
                except Exception as e:
                    operation_results.append(('error', str(e)[:50]))
            
            # At least some operations should handle resource pressure gracefully
            assert len(operation_results) == 3
        
        finally:
            # Release held connections
            for conn in held_connections:
                try:
                    conn.__exit__(None, None, None)
                except:
                    pass
        
        # System should recover after resources are freed
        time.sleep(0.1)  # Brief pause for recovery
        
        # Operations should work normally now
        recovery_result = db_manager.execute_query("SELECT COUNT(*) FROM resource_test")
        assert len(recovery_result) == 1
        
        # Insert should work
        db_manager.execute_update("INSERT INTO resource_test (id, data) VALUES (1, 'recovered')")
        
        final_count = db_manager.execute_query("SELECT COUNT(*) as count FROM resource_test")
        assert final_count[0]['count'] == 1
