"""
Main Flask application factory for InciteRewrite.
Privacy-first legal citation verification system.
"""
import os
from flask import Flask, request, session
from datetime import datetime, timedelta
import hashlib
import logging

from src.config.settings import config
from src.database.models import init_db
from src.api.routes import api_bp

def create_app(config_name=None):
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'default')
    app.config.from_object(config[config_name])
    
    # Initialize logging
    setup_logging(app)
    
    # Initialize database
    init_db(app.config['DATABASE_PATH'])
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Configure session management
    @app.before_request
    def before_request():
        """Handle session management and security checks."""
        # Make sessions permanent with configured timeout
        session.permanent = True
        
        # Check if session has expired
        if 'created_at' in session:
            created_at = datetime.fromisoformat(session['created_at'])
            if datetime.utcnow() - created_at > app.config['SESSION_TIMEOUT']:
                session.clear()
                
        # Set session creation time if new session
        if 'created_at' not in session:
            session['created_at'] = datetime.utcnow().isoformat()
            
        # Log request for audit trail (no document content)
        app.logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
    
    @app.after_request
    def after_request(response):
        """Add security headers."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
    
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        }
    
    return app

def setup_logging(app):
    """Configure application logging."""
    if not app.debug and not app.testing:
        # Production logging setup
        if not os.path.exists('logs'):
            os.mkdir('logs')
            
        file_handler = logging.FileHandler('logs/inciterewrite.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('InciteRewrite startup')

def generate_document_hash(content):
    """Generate SHA256 hash of document content for audit trail."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)