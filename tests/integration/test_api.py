"""
Integration tests for API endpoints.
"""
import pytest
import json
import tempfile
import os
from src.app import create_app
from src.database.models import init_db
from src.citation.courtlistener import init_courtlistener_service

class TestAPIIntegration:
    
    def setup_method(self):
        """Set up test application."""
        self.db_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        
        # Create test app
        self.app = create_app('testing')
        self.app.config['DATABASE_PATH'] = self.db_path
        self.client = self.app.test_client()
        
        # Initialize services
        with self.app.app_context():
            init_db(self.db_path)
            init_courtlistener_service()  # No API key for testing
    
    def teardown_method(self):
        """Clean up test database."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get('/api/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'timestamp' in data['data']
        assert data['data']['status'] == 'healthy'
        assert 'services' in data['data']
    
    def test_analyze_document(self):
        """Test document analysis endpoint."""
        test_document = """
        In Brown v. Board of Education, 347 U.S. 483 (1954), the Supreme Court held that 
        racial segregation in public schools violates the Equal Protection Clause of the 
        Fourteenth Amendment. This decision overturned Plessy v. Ferguson, 163 U.S. 537 (1896).
        
        The court also referenced 42 U.S.C. § 1983 in its analysis.
        """
        
        response = self.client.post('/api/analyze',
                                   json={'document': test_document},
                                   content_type='application/json')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'session_id' in data['data']
        assert data['data']['citations_found'] > 0
        assert data['data']['status'] == 'analysis_complete'
        
        return data['data']['session_id']
    
    def test_verify_citations(self):
        """Test citation verification endpoint."""
        # First analyze document
        test_document = """
        In Miranda v. Arizona, 384 U.S. 436 (1966), the Court established the famous 
        Miranda rights. This case built upon Escobedo v. Illinois, 378 U.S. 478 (1964).
        """
        
        analyze_response = self.client.post('/api/analyze',
                                          json={'document': test_document},
                                          content_type='application/json')
        
        analyze_data = json.loads(analyze_response.data)
        session_id = analyze_data['data']['session_id']
        
        # Now verify citations
        verify_response = self.client.post('/api/verify',
                                         json={
                                             'session_id': session_id,
                                             'document': test_document
                                         },
                                         content_type='application/json')
        
        assert verify_response.status_code == 200
        
        verify_data = json.loads(verify_response.data)
        assert verify_data['success'] == True
        assert verify_data['data']['status'] == 'verification_complete'
        assert 'citations_found' in verify_data['data']
        assert 'citations_verified' in verify_data['data']
        assert 'overall_confidence' in verify_data['data']
    
    def test_get_results(self):
        """Test results retrieval endpoint."""
        # First analyze and verify
        test_document = "See Roe v. Wade, 410 U.S. 113 (1973) for details."
        
        # Analyze
        analyze_response = self.client.post('/api/analyze',
                                          json={'document': test_document},
                                          content_type='application/json')
        session_id = json.loads(analyze_response.data)['data']['session_id']
        
        # Verify
        self.client.post('/api/verify',
                        json={'session_id': session_id, 'document': test_document},
                        content_type='application/json')
        
        # Get results
        results_response = self.client.get(f'/api/results/{session_id}')
        
        assert results_response.status_code == 200
        
        results_data = json.loads(results_response.data)
        assert results_data['success'] == True
        assert 'citations_found' in results_data['data']
        assert 'citation_details' in results_data['data']
        assert len(results_data['data']['citation_details']) > 0
    
    def test_view_session(self):
        """Test session view endpoint."""
        # Create session
        test_document = "Test document with 28 U.S.C. § 1332 jurisdiction."
        
        analyze_response = self.client.post('/api/analyze',
                                          json={'document': test_document},
                                          content_type='application/json')
        session_id = json.loads(analyze_response.data)['data']['session_id']
        
        # View session
        view_response = self.client.get(f'/api/view/{session_id}')
        
        assert view_response.status_code == 200
        
        view_data = json.loads(view_response.data)
        assert view_data['success'] == True
        assert view_data['data']['session_id'] == session_id
        assert 'created_at' in view_data['data']
        assert 'expires_at' in view_data['data']
    
    def test_invalid_session(self):
        """Test handling of invalid session IDs."""
        fake_session_id = '00000000-0000-0000-0000-000000000000'
        
        response = self.client.get(f'/api/results/{fake_session_id}')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'Invalid or expired session' in data['error']['message']
    
    def test_missing_document(self):
        """Test handling of missing document in analysis."""
        response = self.client.post('/api/analyze',
                                   json={},
                                   content_type='application/json')
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'Missing' in data['error']['message']
    
    def test_document_hash_verification(self):
        """Test document hash verification in verify endpoint."""
        original_document = "Original document with 42 U.S.C. § 1983."
        modified_document = "Modified document with 42 U.S.C. § 1983."
        
        # Analyze original
        analyze_response = self.client.post('/api/analyze',
                                          json={'document': original_document},
                                          content_type='application/json')
        session_id = json.loads(analyze_response.data)['data']['session_id']
        
        # Try to verify with modified document
        verify_response = self.client.post('/api/verify',
                                         json={
                                             'session_id': session_id,
                                             'document': modified_document
                                         },
                                         content_type='application/json')
        
        assert verify_response.status_code == 403
        
        verify_data = json.loads(verify_response.data)
        assert verify_data['success'] == False
        assert 'hash mismatch' in verify_data['error']['message'].lower()
    
    def test_content_type_validation(self):
        """Test content type validation."""
        response = self.client.post('/api/analyze',
                                   data='not json',
                                   content_type='text/plain')
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'Content-Type must be application/json' in data['error']['message']