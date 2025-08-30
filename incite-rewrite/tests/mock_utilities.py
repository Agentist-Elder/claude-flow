"""
Mock objects and collaboration patterns for London School TDD.
Provides mock implementations focused on behavior verification and interaction testing.
"""

from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, List, Any, Optional, Callable
import time
import json


class BehaviorVerificationMixin:
    """Mixin for behavior verification in London School TDD style."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interaction_log = []
        self.collaboration_calls = []
    
    def log_interaction(self, method_name: str, args: tuple, kwargs: dict, result: Any = None):
        """Log interaction for behavior verification."""
        self.interaction_log.append({
            'method': method_name,
            'args': args,
            'kwargs': kwargs,
            'result': result,
            'timestamp': time.time()
        })
    
    def verify_collaboration(self, expected_calls: List[str]) -> bool:
        """Verify that expected collaborations occurred in order."""
        actual_calls = [entry['method'] for entry in self.interaction_log]
        return actual_calls == expected_calls
    
    def get_interaction_summary(self) -> Dict[str, Any]:
        """Get summary of all interactions for verification."""
        methods_called = set(entry['method'] for entry in self.interaction_log)
        call_counts = {}
        for entry in self.interaction_log:
            method = entry['method']
            call_counts[method] = call_counts.get(method, 0) + 1
        
        return {
            'total_interactions': len(self.interaction_log),
            'unique_methods': len(methods_called),
            'methods_called': list(methods_called),
            'call_counts': call_counts,
            'interaction_sequence': [entry['method'] for entry in self.interaction_log]
        }


class MockAuthenticationManager(Mock, BehaviorVerificationMixin):
    """Mock authentication manager with behavior verification capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registered_users = {}
        self.active_sessions = {}
        self.session_counter = 1000
    
    def register_user(self, username: str, email: str, password: str):
        """Mock user registration with realistic behavior."""
        self.log_interaction('register_user', (username, email, password), {})
        
        # Simulate duplicate user check
        if username in self.registered_users:
            raise ValueError("User already exists")
        
        # Create mock user object
        user = Mock()
        user.user_id = f"user_{len(self.registered_users) + 1}"
        user.username = username
        user.email = email
        user.created_at = time.time()
        user.is_active = True
        
        self.registered_users[username] = user
        return user
    
    def authenticate_user(self, username: str, password: str):
        """Mock user authentication with realistic behavior."""
        self.log_interaction('authenticate_user', (username, password), {})
        
        user = self.registered_users.get(username)
        if user and password == "TestPassword123!":  # Mock password check
            user.last_login = time.time()
            return True, user
        return False, None
    
    def create_session(self, user_id: str):
        """Mock session creation with realistic behavior."""
        self.log_interaction('create_session', (user_id,), {})
        
        session_token = f"session_{self.session_counter}_{user_id}"
        self.session_counter += 1
        
        self.active_sessions[session_token] = {
            'user_id': user_id,
            'created_at': time.time(),
            'is_active': True
        }
        
        return session_token
    
    def validate_session(self, session_token: str):
        """Mock session validation with realistic behavior."""
        self.log_interaction('validate_session', (session_token,), {})
        
        session = self.active_sessions.get(session_token)
        if session and session['is_active']:
            return True, session['user_id']
        return False, None


class MockTextProcessor(Mock, BehaviorVerificationMixin):
    """Mock text processor with behavior verification capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_documents = {}
        self.analysis_counter = 1
    
    def analyze_text(self, text: str, store_result: bool = True):
        """Mock text analysis with realistic behavior."""
        self.log_interaction('analyze_text', (text, store_result), {})
        
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        
        # Create mock analysis result
        analysis = Mock()
        analysis.word_count = len(text.split())
        analysis.character_count = len(text)
        analysis.sentence_count = text.count('.') + text.count('!') + text.count('?') or 1
        analysis.paragraph_count = text.count('\n\n') + 1
        analysis.avg_word_length = sum(len(word) for word in text.split()) / len(text.split()) if text.split() else 0
        analysis.readability_score = min(100, max(0, 100 - analysis.avg_word_length * 10))
        analysis.sentiment_score = 0.1  # Neutral
        analysis.common_words = {}
        analysis.processing_time = 0.05
        
        if store_result:
            doc_id = f"doc_{self.analysis_counter}"
            self.processed_documents[doc_id] = {
                'text': text,
                'analysis': analysis,
                'stored_at': time.time()
            }
            analysis.doc_id = doc_id
            self.analysis_counter += 1
        
        return analysis
    
    def search_documents_by_word(self, word: str):
        """Mock document search with realistic behavior."""
        self.log_interaction('search_documents_by_word', (word,), {})
        
        results = []
        for doc_id, doc_data in self.processed_documents.items():
            if word.lower() in doc_data['text'].lower():
                results.append({
                    'doc_id': doc_id,
                    'word_count': doc_data['analysis'].word_count,
                    'relevance_score': 0.8
                })
        
        return results


class MockDatabaseManager(Mock, BehaviorVerificationMixin):
    """Mock database manager with behavior verification capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query_log = []
        self.connection_count = 0
        self.error_count = 0
    
    def execute_query(self, query: str, params: tuple = ()):
        """Mock query execution with realistic behavior."""
        self.log_interaction('execute_query', (query, params), {})
        
        self.query_log.append({
            'query': query,
            'params': params,
            'timestamp': time.time(),
            'type': 'SELECT'
        })
        
        # Return mock results based on query type
        if 'COUNT(*)' in query:
            return [{'count': len(self.query_log)}]
        elif 'SELECT' in query.upper():
            return [{'id': 1, 'data': 'mock_data'}]
        else:
            return []
    
    def execute_update(self, query: str, params: tuple = ()):
        """Mock update execution with realistic behavior."""
        self.log_interaction('execute_update', (query, params), {})
        
        self.query_log.append({
            'query': query,
            'params': params,
            'timestamp': time.time(),
            'type': 'UPDATE'
        })
        
        # Return number of affected rows
        return 1
    
    def get_connection(self):
        """Mock connection retrieval with realistic behavior."""
        self.log_interaction('get_connection', (), {})
        
        self.connection_count += 1
        mock_connection = Mock()
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        return mock_connection


class MockCourtListenerClient(Mock, BehaviorVerificationMixin):
    """Mock CourtListener client with behavior verification capabilities."""
    
    def __init__(self, api_key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key
        self.request_count = 0
        self.last_request_time = 0
        self.mock_responses = {}
    
    def search_opinions(self, query: str, court: str = None, **kwargs):
        """Mock opinion search with realistic behavior."""
        self.log_interaction('search_opinions', (query, court), kwargs)
        
        self.request_count += 1
        self.last_request_time = time.time()
        
        # Simulate rate limiting
        time.sleep(0.01)  # Small delay to simulate API call
        
        # Return mock search results
        return {
            'count': 2,
            'results': [
                {
                    'id': 12345,
                    'citation': f'Mock Citation for "{query}"',
                    'case_name': 'Mock Case v. Example',
                    'court': court or 'Mock Court'
                },
                {
                    'id': 12346,
                    'citation': f'Another Citation for "{query}"',
                    'case_name': 'Another Case v. Example',
                    'court': court or 'Mock Court'
                }
            ]
        }
    
    def verify_citation(self, citation: str, citation_type: str = None):
        """Mock citation verification with realistic behavior."""
        self.log_interaction('verify_citation', (citation, citation_type), {})
        
        self.request_count += 1
        self.last_request_time = time.time()
        
        # Simulate verification result based on citation format
        is_valid_format = any(char.isdigit() for char in citation)
        
        return {
            'citation': citation,
            'verified': is_valid_format,
            'confidence_score': 0.9 if is_valid_format else 0.1,
            'matches': [
                {'id': 12345, 'citation': citation}
            ] if is_valid_format else []
        }
    
    def get_api_stats(self):
        """Mock API statistics with realistic behavior."""
        self.log_interaction('get_api_stats', (), {})
        
        return {
            'total_requests': self.request_count,
            'total_errors': 0,
            'error_rate': 0.0,
            'api_key': self.api_key[:8] + '...',  # Partial key for security
            'last_request': self.last_request_time
        }


class CollaborationVerifier:
    """Utility class for verifying object collaborations in London School TDD style."""
    
    @staticmethod
    def verify_method_calls(mock_object, expected_calls: List[call]):
        """Verify that mock object received expected method calls."""
        actual_calls = mock_object.call_args_list
        return actual_calls == expected_calls
    
    @staticmethod
    def verify_collaboration_sequence(mocks: Dict[str, Mock], expected_sequence: List[Dict[str, Any]]):
        """Verify collaboration sequence across multiple mock objects."""
        all_calls = []
        
        for mock_name, mock_obj in mocks.items():
            if hasattr(mock_obj, 'interaction_log'):
                for interaction in mock_obj.interaction_log:
                    all_calls.append({
                        'mock': mock_name,
                        'method': interaction['method'],
                        'timestamp': interaction['timestamp']
                    })
        
        # Sort by timestamp to get chronological order
        all_calls.sort(key=lambda x: x['timestamp'])
        
        # Verify sequence matches expected pattern
        actual_sequence = [{'mock': call['mock'], 'method': call['method']} for call in all_calls]
        return actual_sequence == expected_sequence
    
    @staticmethod
    def verify_interaction_patterns(mock_object, patterns: Dict[str, Any]):
        """Verify interaction patterns match expected behavior."""
        if not hasattr(mock_object, 'interaction_log'):
            return False
        
        summary = mock_object.get_interaction_summary()
        
        for pattern_key, expected_value in patterns.items():
            if pattern_key == 'min_calls':
                if summary['total_interactions'] < expected_value:
                    return False
            elif pattern_key == 'max_calls':
                if summary['total_interactions'] > expected_value:
                    return False
            elif pattern_key == 'required_methods':
                if not all(method in summary['methods_called'] for method in expected_value):
                    return False
            elif pattern_key == 'call_sequence':
                if summary['interaction_sequence'] != expected_value:
                    return False
        
        return True


class MockFactory:
    """Factory for creating configured mock objects with behavior verification."""
    
    @staticmethod
    def create_auth_manager(users: List[Dict[str, str]] = None) -> MockAuthenticationManager:
        """Create configured mock authentication manager."""
        mock_auth = MockAuthenticationManager()
        
        if users:
            for user_data in users:
                mock_auth.register_user(
                    user_data['username'],
                    user_data['email'],
                    user_data['password']
                )
        
        return mock_auth
    
    @staticmethod
    def create_text_processor(documents: List[str] = None) -> MockTextProcessor:
        """Create configured mock text processor."""
        mock_processor = MockTextProcessor()
        
        if documents:
            for doc in documents:
                mock_processor.analyze_text(doc, store_result=True)
        
        return mock_processor
    
    @staticmethod
    def create_db_manager(initial_data: Dict[str, List] = None) -> MockDatabaseManager:
        """Create configured mock database manager."""
        mock_db = MockDatabaseManager()
        
        if initial_data:
            for table, rows in initial_data.items():
                for row in rows:
                    mock_db.execute_update(
                        f"INSERT INTO {table} VALUES (?)",
                        (json.dumps(row),)
                    )
        
        return mock_db
    
    @staticmethod
    def create_courtlistener_client(api_key: str = "test_key", 
                                   responses: Dict[str, Any] = None) -> MockCourtListenerClient:
        """Create configured mock CourtListener client."""
        mock_client = MockCourtListenerClient(api_key)
        
        if responses:
            mock_client.mock_responses = responses
        
        return mock_client
    
    @staticmethod
    def create_integrated_mocks(scenario: str = "default") -> Dict[str, Mock]:
        """Create set of integrated mocks for common testing scenarios."""
        
        if scenario == "user_workflow":
            return {
                'auth_manager': MockFactory.create_auth_manager([
                    {'username': 'testuser', 'email': 'test@example.com', 'password': 'password123'}
                ]),
                'text_processor': MockFactory.create_text_processor([
                    "Sample document for testing"
                ]),
                'db_manager': MockFactory.create_db_manager(),
                'api_client': MockFactory.create_courtlistener_client()
            }
        
        elif scenario == "legal_processing":
            return {
                'text_processor': MockFactory.create_text_processor([
                    "Brown v. Board, 347 U.S. 483 (1954), landmark case"
                ]),
                'citation_extractor': Mock(),
                'api_client': MockFactory.create_courtlistener_client(),
                'db_manager': MockFactory.create_db_manager()
            }
        
        else:  # default scenario
            return {
                'auth_manager': MockFactory.create_auth_manager(),
                'text_processor': MockFactory.create_text_processor(),
                'db_manager': MockFactory.create_db_manager(),
                'api_client': MockFactory.create_courtlistener_client()
            }


# Context manager for behavior verification
class BehaviorVerificationContext:
    """Context manager for verifying behavior in London School TDD style."""
    
    def __init__(self, mocks: Dict[str, Mock]):
        self.mocks = mocks
        self.start_time = None
        self.verifications = []
    
    def __enter__(self):
        self.start_time = time.time()
        # Reset interaction logs
        for mock_obj in self.mocks.values():
            if hasattr(mock_obj, 'interaction_log'):
                mock_obj.interaction_log.clear()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Perform final verifications
        end_time = time.time()
        duration = end_time - self.start_time
        
        # Log verification summary
        verification_summary = {
            'duration': duration,
            'mocks_verified': len(self.mocks),
            'verifications_passed': len([v for v in self.verifications if v['passed']]),
            'verifications_failed': len([v for v in self.verifications if not v['passed']])
        }
        
        return False  # Don't suppress exceptions
    
    def verify_collaboration(self, mock_name: str, expected_calls: List[str]):
        """Verify collaboration pattern for specific mock."""
        mock_obj = self.mocks.get(mock_name)
        if mock_obj and hasattr(mock_obj, 'verify_collaboration'):
            result = mock_obj.verify_collaboration(expected_calls)
            self.verifications.append({
                'type': 'collaboration',
                'mock': mock_name,
                'expected': expected_calls,
                'passed': result
            })
            return result
        return False
    
    def verify_interaction_count(self, mock_name: str, min_count: int = None, max_count: int = None):
        """Verify interaction count for specific mock."""
        mock_obj = self.mocks.get(mock_name)
        if mock_obj and hasattr(mock_obj, 'interaction_log'):
            count = len(mock_obj.interaction_log)
            passed = True
            
            if min_count is not None and count < min_count:
                passed = False
            if max_count is not None and count > max_count:
                passed = False
            
            self.verifications.append({
                'type': 'interaction_count',
                'mock': mock_name,
                'actual_count': count,
                'passed': passed
            })
            
            return passed
        return False