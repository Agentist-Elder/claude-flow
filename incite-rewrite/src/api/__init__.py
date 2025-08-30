"""
API endpoints for authentication and text processing.
Real HTTP responses and database operations without mocks.
"""

from .endpoints import create_app, benchmark_endpoint

__all__ = ['create_app', 'benchmark_endpoint']