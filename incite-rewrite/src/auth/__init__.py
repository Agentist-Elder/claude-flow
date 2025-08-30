"""
Authentication module with real hash validation and user management.
Following London School TDD principles with behavior-focused testing.
"""

from .authentication import AuthenticationManager, AuthenticationError, User

__all__ = ['AuthenticationManager', 'AuthenticationError', 'User']