"""
Response utilities for consistent API responses.
"""
from flask import jsonify
from datetime import datetime
from typing import Dict, Any, Optional

def create_response(data: Dict[str, Any], status_code: int = 200) -> tuple:
    """Create standardized successful response."""
    response_data = {
        'success': True,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    return jsonify(response_data), status_code

def create_error_response(message: str, status_code: int = 400, 
                         error_code: Optional[str] = None) -> tuple:
    """Create standardized error response."""
    response_data = {
        'success': False,
        'timestamp': datetime.utcnow().isoformat(),
        'error': {
            'message': message,
            'code': error_code or f'E{status_code}',
            'status_code': status_code
        }
    }
    return jsonify(response_data), status_code