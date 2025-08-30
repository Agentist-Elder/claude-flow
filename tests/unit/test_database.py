"""
Unit tests for database operations.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from src.database.models import Database, SessionManager, ResultsManager, init_db

class TestDatabase:
    
    def setup_method(self):
        """Set up test database."""
        self.db_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        
        init_db(self.db_path)
    
    def teardown_method(self):
        """Clean up test database."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_session_creation(self):
        """Test session creation."""
        document_hash = "test_hash_123"
        session_id = SessionManager.create_session(document_hash)
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        
        # Verify session can be retrieved
        session_data = SessionManager.get_session(session_id)
        assert session_data is not None
        assert session_data['document_hash'] == document_hash
        assert session_data['status'] == 'active'
    
    def test_session_expiry(self):
        """Test session expiry logic."""
        document_hash = "test_hash_456"
        session_id = SessionManager.create_session(document_hash)
        
        # Verify session exists initially
        session_data = SessionManager.get_session(session_id)
        assert session_data is not None
        assert session_data['status'] == 'active'
        
        # Manually expire the session
        SessionManager.expire_session(session_id)
        
        # Should not be retrievable after expiry
        session_data = SessionManager.get_session(session_id)
        assert session_data is None
    
    def test_results_storage(self):
        """Test results storage and retrieval."""
        # Create session first
        document_hash = "test_hash_789"
        session_id = SessionManager.create_session(document_hash)
        
        # Store results
        result_id = ResultsManager.store_result(
            session_id=session_id,
            document_hash=document_hash,
            citations_found=5,
            citations_verified=4,
            confidence_score=0.85,
            verification_details="Test verification"
        )
        
        assert result_id is not None
        
        # Retrieve results
        results = ResultsManager.get_results(session_id)
        assert results is not None
        assert results['citations_found'] == 5
        assert results['citations_verified'] == 4
        assert results['confidence_score'] == 0.85
    
    def test_citation_details_storage(self):
        """Test storage of individual citation details."""
        # Create session and result
        document_hash = "test_hash_details"
        session_id = SessionManager.create_session(document_hash)
        result_id = ResultsManager.store_result(
            session_id=session_id,
            document_hash=document_hash,
            citations_found=1,
            citations_verified=1,
            confidence_score=0.9
        )
        
        # Store citation detail
        ResultsManager.store_citation_detail(
            result_id=result_id,
            citation_text="347 U.S. 483 (1954)",
            citation_type="case_citation",
            verified=True,
            confidence_score=0.9,
            courtlistener_match='{"case_name": "Brown v. Board"}',
            error_message=None
        )
        
        # Retrieve citation details
        details = ResultsManager.get_citation_details(result_id)
        assert len(details) == 1
        assert details[0]['citation_text'] == "347 U.S. 483 (1954)"
        assert details[0]['verified'] == True
        assert details[0]['confidence_score'] == 0.9
    
    def test_session_cleanup(self):
        """Test cleanup of expired sessions."""
        # Create session
        document_hash = "test_hash_cleanup"
        session_id = SessionManager.create_session(document_hash)
        
        # Create results
        result_id = ResultsManager.store_result(
            session_id=session_id,
            document_hash=document_hash,
            citations_found=1,
            citations_verified=1,
            confidence_score=0.8
        )
        
        # Add citation details
        ResultsManager.store_citation_detail(
            result_id=result_id,
            citation_text="Test Citation",
            citation_type="case_citation",
            verified=True,
            confidence_score=0.8
        )
        
        # Manually expire session
        SessionManager.expire_session(session_id)
        
        # Run cleanup
        SessionManager.cleanup_expired_sessions()
        
        # Verify everything is cleaned up
        session_data = SessionManager.get_session(session_id)
        assert session_data is None
        
        results = ResultsManager.get_results(session_id)
        assert results is None
        
        citation_details = ResultsManager.get_citation_details(result_id)
        assert len(citation_details) == 0