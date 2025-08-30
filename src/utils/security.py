"""
Security utilities for InciteRewrite application.
"""
from functools import wraps
from flask import request, session, current_app
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def require_session(f):
    """Decorator to require valid session for endpoint access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'current_session_id' not in session and not request.is_json:
            return {'error': 'Valid session required'}, 401
        return f(*args, **kwargs)
    return decorated_function

def validate_document_size(document_text: str) -> bool:
    """Validate document size against configured limits."""
    max_size = current_app.config.get('MAX_DOCUMENT_SIZE', 10 * 1024 * 1024)
    return len(document_text.encode('utf-8')) <= max_size

def sanitize_input(text: str) -> str:
    """Basic input sanitization."""
    if not text:
        return ""
    
    # Remove null bytes and control characters except newlines/tabs
    sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    return sanitized.strip()

def validate_session_id(session_id: str) -> bool:
    """Validate session ID format."""
    if not session_id or len(session_id) != 36:
        return False
    
    # Check UUID format
    import re
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    return bool(uuid_pattern.match(session_id))