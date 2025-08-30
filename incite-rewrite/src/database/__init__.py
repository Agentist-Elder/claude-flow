"""
Database connection and operations layer.
Real database testing without mocks for London School TDD.
"""

from .connection import DatabaseManager, DatabaseStats

__all__ = ['DatabaseManager', 'DatabaseStats']