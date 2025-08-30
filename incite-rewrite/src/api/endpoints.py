"""
API endpoints for authentication and text processing.
Following London School TDD with real HTTP responses and database operations.
"""

from flask import Flask, request, jsonify, session
from flask_cors import CORS
import sqlite3
import json
import time
from typing import Dict, Any, Optional
import logging
from functools import wraps

from ..auth.authentication import AuthenticationManager, AuthenticationError
from ..utils.text_processing import TextProcessor


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom API error with status code."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def create_app(test_config: Optional[Dict] = None) -> Flask:
    """
    Create Flask application with real endpoints and middleware.
    Tests validate actual HTTP behavior and database interactions.
    """
    app = Flask(__name__)
    
    # Configuration
    if test_config:
        app.config.update(test_config)
    else:
        app.config.update({
            'SECRET_KEY': 'dev-secret-key-change-in-production',
            'DATABASE_PATH': ':memory:',
            'TESTING': False
        })
    
    CORS(app)
    
    # Initialize services
    auth_manager = AuthenticationManager(app.config.get('DATABASE_PATH', ':memory:'))
    text_processor = TextProcessor(app.config.get('DATABASE_PATH', ':memory:'))
    
    # Error handlers
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = {'error': error.message}
        return jsonify(response), error.status_code
    
    @app.errorhandler(AuthenticationError)
    def handle_auth_error(error):
        response = {'error': str(error)}
        return jsonify(response), 401
    
    @app.errorhandler(ValueError)
    def handle_value_error(error):
        response = {'error': str(error)}
        return jsonify(response), 400
    
    @app.errorhandler(Exception)
    def handle_general_error(error):
        logger.error(f"Unexpected error: {str(error)}")
        response = {'error': 'Internal server error'}
        return jsonify(response), 500
    
    # Authentication middleware
    def require_auth(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                raise APIError('Missing or invalid authorization header', 401)
            
            session_token = auth_header.replace('Bearer ', '')
            is_valid, user_id = auth_manager.validate_session(session_token)
            
            if not is_valid:
                raise APIError('Invalid or expired session', 401)
            
            request.user_id = user_id
            return f(*args, **kwargs)
        
        return decorated_function
    
    # Performance tracking middleware
    @app.before_request
    def before_request():
        request.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        duration = time.time() - getattr(request, 'start_time', time.time())
        response.headers['X-Response-Time'] = f"{duration:.3f}s"
        
        # Log API usage
        logger.info(f"{request.method} {request.path} - {response.status_code} - {duration:.3f}s")
        return response
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for monitoring."""
        try:
            # Test database connection
            with sqlite3.connect(app.config.get('DATABASE_PATH', ':memory:')) as conn:
                conn.execute('SELECT 1').fetchone()
            
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'version': '1.0.0'
            })
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }), 503
    
    # Authentication endpoints
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        """Register a new user."""
        data = request.get_json()
        if not data:
            raise APIError('JSON data required')
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not all([username, email, password]):
            raise APIError('Username, email, and password are required')
        
        try:
            user = auth_manager.register_user(username, email, password)
            session_token = auth_manager.create_session(user.user_id)
            
            return jsonify({
                'success': True,
                'user': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.created_at
                },
                'session_token': session_token
            }), 201
        
        except AuthenticationError as e:
            raise APIError(str(e), 400)
    
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """Authenticate user credentials."""
        data = request.get_json()
        if not data:
            raise APIError('JSON data required')
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            raise APIError('Username and password are required')
        
        success, user = auth_manager.authenticate_user(username, password)
        
        if not success or not user:
            raise APIError('Invalid credentials', 401)
        
        session_token = auth_manager.create_session(user.user_id)
        
        return jsonify({
            'success': True,
            'user': {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'last_login': user.last_login
            },
            'session_token': session_token
        })
    
    @app.route('/api/auth/profile', methods=['GET'])
    @require_auth
    def get_profile():
        """Get user profile information."""
        user = auth_manager.get_user_by_id(request.user_id)
        if not user:
            raise APIError('User not found', 404)
        
        return jsonify({
            'user': {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at,
                'last_login': user.last_login,
                'is_active': user.is_active
            }
        })
    
    @app.route('/api/auth/validate', methods=['POST'])
    def validate_session():
        """Validate session token."""
        data = request.get_json()
        if not data:
            raise APIError('JSON data required')
        
        session_token = data.get('session_token', '')
        if not session_token:
            raise APIError('Session token required')
        
        is_valid, user_id = auth_manager.validate_session(session_token)
        
        return jsonify({
            'valid': is_valid,
            'user_id': user_id if is_valid else None
        })
    
    # Text processing endpoints
    @app.route('/api/text/analyze', methods=['POST'])
    @require_auth
    def analyze_text():
        """Analyze text content."""
        data = request.get_json()
        if not data:
            raise APIError('JSON data required')
        
        text = data.get('text', '')
        store_result = data.get('store_result', True)
        
        if not text:
            raise APIError('Text content is required')
        
        if len(text) > 100000:  # 100KB limit
            raise APIError('Text content too large (max 100KB)', 413)
        
        try:
            analysis = text_processor.analyze_text(text, store_result)
            
            return jsonify({
                'success': True,
                'analysis': {
                    'word_count': analysis.word_count,
                    'character_count': analysis.character_count,
                    'sentence_count': analysis.sentence_count,
                    'paragraph_count': analysis.paragraph_count,
                    'avg_word_length': round(analysis.avg_word_length, 2),
                    'readability_score': round(analysis.readability_score, 2),
                    'common_words': analysis.common_words,
                    'sentiment_score': round(analysis.sentiment_score, 3),
                    'processing_time': round(analysis.processing_time, 4)
                }
            })
        
        except ValueError as e:
            raise APIError(str(e), 400)
    
    @app.route('/api/text/clean', methods=['POST'])
    @require_auth
    def clean_text():
        """Clean and normalize text."""
        data = request.get_json()
        if not data:
            raise APIError('JSON data required')
        
        text = data.get('text', '')
        if not text:
            raise APIError('Text content is required')
        
        try:
            cleaned = text_processor.clean_text(text)
            return jsonify({
                'success': True,
                'original_length': len(text),
                'cleaned_length': len(cleaned),
                'cleaned_text': cleaned
            })
        except ValueError as e:
            raise APIError(str(e), 400)
    
    @app.route('/api/text/search', methods=['GET'])
    @require_auth
    def search_text():
        """Search documents by word."""
        word = request.args.get('word', '').strip()
        if not word:
            raise APIError('Search word parameter is required')
        
        results = text_processor.search_documents_by_word(word)
        
        return jsonify({
            'success': True,
            'word': word,
            'results_count': len(results),
            'results': results
        })
    
    @app.route('/api/text/document/<doc_id>', methods=['GET'])
    @require_auth
    def get_document(doc_id: str):
        """Get document analysis by ID."""
        document = text_processor.get_document_analysis(doc_id)
        
        if not document:
            raise APIError('Document not found', 404)
        
        return jsonify({
            'success': True,
            'document': document
        })
    
    # Analytics endpoints
    @app.route('/api/analytics/stats', methods=['GET'])
    @require_auth
    def get_analytics_stats():
        """Get system analytics and usage statistics."""
        try:
            with sqlite3.connect(app.config.get('DATABASE_PATH', ':memory:')) as conn:
                # User statistics
                user_stats = conn.execute("""
                    SELECT COUNT(*) as total_users,
                           COUNT(CASE WHEN last_login > ? THEN 1 END) as active_users
                    FROM users
                """, (time.time() - 30*24*3600,)).fetchone()  # Active in last 30 days
                
                # Document statistics
                doc_stats = conn.execute("""
                    SELECT COUNT(*) as total_documents,
                           AVG(word_count) as avg_word_count,
                           SUM(word_count) as total_words
                    FROM text_documents
                """).fetchone()
                
                # Session statistics
                session_stats = conn.execute("""
                    SELECT COUNT(*) as total_sessions,
                           COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_sessions
                    FROM auth_sessions
                """).fetchone()
                
                return jsonify({
                    'success': True,
                    'stats': {
                        'users': {
                            'total': user_stats[0],
                            'active_monthly': user_stats[1]
                        },
                        'documents': {
                            'total': doc_stats[0] or 0,
                            'avg_word_count': round(doc_stats[1] or 0, 2),
                            'total_words': doc_stats[2] or 0
                        },
                        'sessions': {
                            'total': session_stats[0],
                            'active': session_stats[1]
                        }
                    }
                })
        
        except Exception as e:
            logger.error(f"Analytics error: {str(e)}")
            raise APIError('Failed to retrieve analytics', 500)
    
    return app


# Performance testing helper
def benchmark_endpoint(app: Flask, endpoint: str, data: Dict[str, Any] = None, 
                      headers: Dict[str, str] = None, iterations: int = 10) -> Dict[str, float]:
    """
    Benchmark API endpoint performance for testing.
    Returns timing statistics for performance validation.
    """
    with app.test_client() as client:
        times = []
        
        for _ in range(iterations):
            start_time = time.time()
            
            if data:
                response = client.post(endpoint, json=data, headers=headers)
            else:
                response = client.get(endpoint, headers=headers)
            
            end_time = time.time()
            times.append(end_time - start_time)
        
        return {
            'min_time': min(times),
            'max_time': max(times),
            'avg_time': sum(times) / len(times),
            'total_time': sum(times)
        }