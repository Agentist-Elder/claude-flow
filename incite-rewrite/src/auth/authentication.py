"""
Authentication module with hash validation and user management.
Following London School TDD principles with real behavior validation.
"""

import hashlib
import secrets
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
import sqlite3
import os


@dataclass
class User:
    """User model with authentication data."""
    user_id: str
    username: str
    email: str
    password_hash: str
    salt: str
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    is_active: bool = True


class AuthenticationError(Exception):
    """Custom exception for authentication failures."""
    pass


class AuthenticationManager:
    """
    Authentication manager with real hash validation and database operations.
    No mocks - tests real behavior and collaborations.
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the authentication database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_login REAL,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            conn.commit()
    
    def _generate_salt(self) -> str:
        """Generate a cryptographically secure salt."""
        return secrets.token_hex(32)
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt using SHA-256."""
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def register_user(self, username: str, email: str, password: str) -> User:
        """
        Register a new user with proper validation and hash generation.
        Tests will validate real database operations and hash security.
        """
        if len(password) < 8:
            raise AuthenticationError("Password must be at least 8 characters")
        
        if "@" not in email:
            raise AuthenticationError("Invalid email format")
        
        user_id = secrets.token_urlsafe(16)
        salt = self._generate_salt()
        password_hash = self._hash_password(password, salt)
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            salt=salt
        )
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO users (user_id, username, email, password_hash, salt, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user.user_id, user.username, user.email, user.password_hash, 
                     user.salt, user.created_at, user.is_active))
                conn.commit()
        except sqlite3.IntegrityError as e:
            if "username" in str(e):
                raise AuthenticationError("Username already exists")
            elif "email" in str(e):
                raise AuthenticationError("Email already registered")
            else:
                raise AuthenticationError("Registration failed")
        
        return user
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[User]]:
        """
        Authenticate user credentials with real hash validation.
        Returns tuple of (success, user_object).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, username, email, password_hash, salt, created_at, last_login, is_active
                FROM users WHERE username = ? AND is_active = 1
            """, (username,))
            row = cursor.fetchone()
            
            if not row:
                return False, None
            
            user = User(
                user_id=row[0],
                username=row[1],
                email=row[2],
                password_hash=row[3],
                salt=row[4],
                created_at=row[5],
                last_login=row[6],
                is_active=bool(row[7])
            )
            
            # Validate password hash
            expected_hash = self._hash_password(password, user.salt)
            if expected_hash != user.password_hash:
                return False, None
            
            # Update last login
            current_time = time.time()
            conn.execute("""
                UPDATE users SET last_login = ? WHERE user_id = ?
            """, (current_time, user.user_id))
            conn.commit()
            
            user.last_login = current_time
            return True, user
    
    def create_session(self, user_id: str, duration_hours: int = 24) -> str:
        """Create an authentication session."""
        session_id = secrets.token_urlsafe(32)
        created_at = time.time()
        expires_at = created_at + (duration_hours * 3600)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO auth_sessions (session_id, user_id, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, created_at, expires_at, True))
            conn.commit()
        
        return session_id
    
    def validate_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """Validate session and return user_id if valid."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, expires_at FROM auth_sessions 
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return False, None
            
            user_id, expires_at = row
            if time.time() > expires_at:
                # Expire the session
                conn.execute("""
                    UPDATE auth_sessions SET is_active = 0 WHERE session_id = ?
                """, (session_id,))
                conn.commit()
                return False, None
            
            return True, user_id
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, username, email, password_hash, salt, created_at, last_login, is_active
                FROM users WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return User(
                user_id=row[0],
                username=row[1],
                email=row[2],
                password_hash=row[3],
                salt=row[4],
                created_at=row[5],
                last_login=row[6],
                is_active=bool(row[7])
            )