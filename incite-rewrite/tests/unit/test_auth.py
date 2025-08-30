"""
Unit tests for authentication module using London School TDD methodology.
Tests focus on real behavior validation without mocks - testing actual collaborations.
"""

import pytest
import sqlite3
import tempfile
import os
import time
import hashlib
import secrets
from typing import Dict, Any

from src.auth.authentication import (
    AuthenticationManager, 
    AuthenticationError, 
    User
)


class TestAuthenticationManager:
    """
    London School TDD tests for AuthenticationManager.
    Tests real database operations, hash validation, and behavior verification.
    """
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def auth_manager(self, temp_db_path):
        """Create AuthenticationManager with real database."""
        return AuthenticationManager(temp_db_path)
    
    @pytest.fixture
    def memory_auth_manager(self):
        """Create AuthenticationManager with in-memory database."""
        return AuthenticationManager(":memory:")
    
    def test_database_initialization_creates_tables(self, auth_manager, temp_db_path):
        """Test that database initialization creates proper tables with correct schema."""
        # Verify tables exist with correct structure
        with sqlite3.connect(temp_db_path) as conn:
            # Check users table
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            expected_columns = {
                'user_id': 'TEXT',
                'username': 'TEXT',
                'email': 'TEXT', 
                'password_hash': 'TEXT',
                'salt': 'TEXT',
                'created_at': 'REAL',
                'last_login': 'REAL',
                'is_active': 'BOOLEAN'
            }
            
            for col, col_type in expected_columns.items():
                assert col in columns
                assert columns[col] == col_type
            
            # Check auth_sessions table
            cursor = conn.execute("PRAGMA table_info(auth_sessions)")
            session_columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'session_id' in session_columns
            assert 'user_id' in session_columns
            assert 'expires_at' in session_columns
    
    def test_salt_generation_produces_unique_values(self, auth_manager):
        """Test that salt generation produces unique, secure values."""
        salts = set()
        
        # Generate multiple salts and verify uniqueness
        for _ in range(100):
            salt = auth_manager._generate_salt()
            assert salt not in salts, "Salt collision detected"
            assert len(salt) == 64, "Salt should be 32 bytes hex encoded (64 chars)"
            salts.add(salt)
        
        # Verify salts contain only hex characters
        for salt in list(salts)[:10]:  # Check first 10
            assert all(c in '0123456789abcdef' for c in salt)
    
    def test_password_hashing_produces_consistent_results(self, auth_manager):
        """Test password hashing consistency and security."""
        password = "test_password_123"
        salt = "fixed_salt_for_testing"
        
        # Same password + salt should produce same hash
        hash1 = auth_manager._hash_password(password, salt)
        hash2 = auth_manager._hash_password(password, salt)
        assert hash1 == hash2
        
        # Different salt should produce different hash
        different_salt = "different_salt_for_testing"
        hash3 = auth_manager._hash_password(password, different_salt)
        assert hash1 != hash3
        
        # Hash should be SHA-256 (64 hex chars)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)
        
        # Verify actual SHA-256 calculation
        expected_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        assert hash1 == expected_hash
    
    def test_user_registration_success_creates_database_record(self, auth_manager, temp_db_path):
        """Test successful user registration creates proper database records."""
        username = "testuser"
        email = "test@example.com"
        password = "secure_password_123"
        
        # Register user
        user = auth_manager.register_user(username, email, password)
        
        # Verify returned User object
        assert isinstance(user, User)
        assert user.username == username
        assert user.email == email
        assert user.user_id
        assert user.salt
        assert user.password_hash
        assert user.created_at > 0
        assert user.is_active is True
        assert user.last_login is None
        
        # Verify database record
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, username, email, password_hash, salt, is_active
                FROM users WHERE username = ?
            """, (username,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == user.user_id
            assert row[1] == username
            assert row[2] == email
            assert row[3] == user.password_hash
            assert row[4] == user.salt
            assert row[5] == 1  # is_active
        
        # Verify password hash is correct
        expected_hash = hashlib.sha256((password + user.salt).encode()).hexdigest()
        assert user.password_hash == expected_hash
    
    def test_user_registration_validates_input_requirements(self, auth_manager):
        """Test user registration validates all input requirements."""
        # Test password length validation
        with pytest.raises(AuthenticationError, match="Password must be at least 8 characters"):
            auth_manager.register_user("user", "test@example.com", "short")
        
        # Test email format validation
        with pytest.raises(AuthenticationError, match="Invalid email format"):
            auth_manager.register_user("user", "invalid-email", "password123")
        
        # Test empty values
        with pytest.raises(AuthenticationError):
            auth_manager.register_user("", "test@example.com", "password123")
    
    def test_user_registration_prevents_duplicate_usernames(self, auth_manager):
        """Test that duplicate usernames are prevented."""
        username = "duplicate_user"
        email1 = "user1@example.com"
        email2 = "user2@example.com"
        password = "password123"
        
        # First registration should succeed
        user1 = auth_manager.register_user(username, email1, password)
        assert user1.username == username
        
        # Second registration with same username should fail
        with pytest.raises(AuthenticationError, match="Username already exists"):
            auth_manager.register_user(username, email2, password)
    
    def test_user_registration_prevents_duplicate_emails(self, auth_manager):
        """Test that duplicate emails are prevented."""
        username1 = "user1"
        username2 = "user2" 
        email = "duplicate@example.com"
        password = "password123"
        
        # First registration should succeed
        user1 = auth_manager.register_user(username1, email, password)
        assert user1.email == email
        
        # Second registration with same email should fail
        with pytest.raises(AuthenticationError, match="Email already registered"):
            auth_manager.register_user(username2, email, password)
    
    def test_user_authentication_success_with_correct_credentials(self, auth_manager):
        """Test successful authentication with correct credentials."""
        username = "auth_test_user"
        email = "auth@example.com"
        password = "correct_password_123"
        
        # Register user first
        registered_user = auth_manager.register_user(username, email, password)
        initial_login_time = registered_user.last_login
        
        # Authenticate with correct credentials
        success, authenticated_user = auth_manager.authenticate_user(username, password)
        
        # Verify authentication success
        assert success is True
        assert authenticated_user is not None
        assert authenticated_user.user_id == registered_user.user_id
        assert authenticated_user.username == username
        assert authenticated_user.email == email
        
        # Verify last_login was updated
        assert authenticated_user.last_login is not None
        assert authenticated_user.last_login != initial_login_time
        assert authenticated_user.last_login > time.time() - 5  # Within last 5 seconds
    
    def test_user_authentication_failure_with_incorrect_password(self, auth_manager):
        """Test authentication failure with incorrect password."""
        username = "auth_fail_user"
        email = "authfail@example.com"
        correct_password = "correct_password_123"
        wrong_password = "wrong_password_123"
        
        # Register user
        auth_manager.register_user(username, email, correct_password)
        
        # Attempt authentication with wrong password
        success, user = auth_manager.authenticate_user(username, wrong_password)
        
        assert success is False
        assert user is None
    
    def test_user_authentication_failure_with_nonexistent_user(self, auth_manager):
        """Test authentication failure with non-existent user."""
        success, user = auth_manager.authenticate_user("nonexistent", "password123")
        
        assert success is False
        assert user is None
    
    def test_session_creation_generates_valid_session_token(self, auth_manager):
        """Test session creation generates valid tokens and database records."""
        # Register user first
        user = auth_manager.register_user("session_user", "session@example.com", "password123")
        
        # Create session
        session_token = auth_manager.create_session(user.user_id, duration_hours=24)
        
        # Verify session token format
        assert isinstance(session_token, str)
        assert len(session_token) > 20  # Should be a substantial token
        
        # Verify database record creation
        with sqlite3.connect(auth_manager.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, expires_at, is_active FROM auth_sessions
                WHERE session_id = ?
            """, (session_token,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == user.user_id
            assert row[1] > time.time()  # Should expire in the future
            assert row[2] == 1  # Should be active
    
    def test_session_validation_with_valid_active_session(self, auth_manager):
        """Test session validation with valid, non-expired session."""
        # Register user and create session
        user = auth_manager.register_user("valid_session_user", "valid@example.com", "password123")
        session_token = auth_manager.create_session(user.user_id, duration_hours=1)
        
        # Validate session
        is_valid, validated_user_id = auth_manager.validate_session(session_token)
        
        assert is_valid is True
        assert validated_user_id == user.user_id
    
    def test_session_validation_with_expired_session(self, auth_manager):
        """Test session validation with expired session."""
        # Register user and create session with very short duration
        user = auth_manager.register_user("expired_session_user", "expired@example.com", "password123")
        session_token = auth_manager.create_session(user.user_id, duration_hours=-1)  # Expired
        
        # Validate expired session
        is_valid, user_id = auth_manager.validate_session(session_token)
        
        assert is_valid is False
        assert user_id is None
        
        # Verify session was marked as inactive in database
        with sqlite3.connect(auth_manager.db_path) as conn:
            cursor = conn.execute("""
                SELECT is_active FROM auth_sessions WHERE session_id = ?
            """, (session_token,))
            row = cursor.fetchone()
            assert row[0] == 0  # Should be inactive
    
    def test_session_validation_with_invalid_token(self, auth_manager):
        """Test session validation with invalid/non-existent token."""
        is_valid, user_id = auth_manager.validate_session("invalid_token_12345")
        
        assert is_valid is False
        assert user_id is None
    
    def test_get_user_by_id_returns_correct_user(self, auth_manager):
        """Test retrieving user by ID returns correct user data."""
        # Register user
        original_user = auth_manager.register_user("get_user_test", "getuser@example.com", "password123")
        
        # Retrieve user by ID
        retrieved_user = auth_manager.get_user_by_id(original_user.user_id)
        
        assert retrieved_user is not None
        assert retrieved_user.user_id == original_user.user_id
        assert retrieved_user.username == original_user.username
        assert retrieved_user.email == original_user.email
        assert retrieved_user.password_hash == original_user.password_hash
        assert retrieved_user.salt == original_user.salt
        assert retrieved_user.created_at == original_user.created_at
        assert retrieved_user.is_active == original_user.is_active
    
    def test_get_user_by_id_returns_none_for_invalid_id(self, auth_manager):
        """Test retrieving user with invalid ID returns None."""
        user = auth_manager.get_user_by_id("invalid_user_id_12345")
        assert user is None
    
    def test_concurrent_user_registration_maintains_data_integrity(self, auth_manager):
        """Test concurrent operations maintain database integrity."""
        import threading
        import concurrent.futures
        
        results = []
        errors = []
        
        def register_user_thread(index):
            try:
                user = auth_manager.register_user(
                    f"concurrent_user_{index}",
                    f"user{index}@example.com", 
                    "password123"
                )
                results.append(user)
            except Exception as e:
                errors.append(e)
        
        # Run concurrent registrations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_user_thread, i) for i in range(20)]
            concurrent.futures.wait(futures)
        
        # Verify all registrations succeeded
        assert len(results) == 20
        assert len(errors) == 0
        
        # Verify all users have unique IDs
        user_ids = [user.user_id for user in results]
        assert len(set(user_ids)) == 20
    
    def test_authentication_workflow_integration(self, auth_manager):
        """Test complete authentication workflow from registration to session validation."""
        # Step 1: Register user
        username = "workflow_user"
        email = "workflow@example.com"
        password = "workflow_password_123"
        
        user = auth_manager.register_user(username, email, password)
        assert user.username == username
        
        # Step 2: Authenticate user
        success, auth_user = auth_manager.authenticate_user(username, password)
        assert success is True
        assert auth_user.user_id == user.user_id
        
        # Step 3: Create session
        session_token = auth_manager.create_session(auth_user.user_id)
        assert session_token is not None
        
        # Step 4: Validate session
        is_valid, session_user_id = auth_manager.validate_session(session_token)
        assert is_valid is True
        assert session_user_id == user.user_id
        
        # Step 5: Retrieve user by ID
        final_user = auth_manager.get_user_by_id(session_user_id)
        assert final_user.username == username
        assert final_user.email == email
    
    def test_password_security_requirements(self, auth_manager):
        """Test password security and hash strength."""
        password = "security_test_password_123"
        user = auth_manager.register_user("security_user", "security@example.com", password)
        
        # Verify hash properties
        assert len(user.password_hash) == 64  # SHA-256 hex
        assert len(user.salt) == 64  # 32 bytes hex encoded
        
        # Verify hash is different from password
        assert user.password_hash != password
        assert user.salt not in user.password_hash
        
        # Verify hash can't be reversed (different passwords with same salt produce different hashes)
        wrong_password = "wrong_password_123"
        wrong_hash = auth_manager._hash_password(wrong_password, user.salt)
        assert wrong_hash != user.password_hash
    
    def test_database_constraint_enforcement(self, auth_manager, temp_db_path):
        """Test that database constraints are properly enforced."""
        # Test unique username constraint
        auth_manager.register_user("constraint_user", "user1@example.com", "password123")
        
        with pytest.raises(AuthenticationError):
            auth_manager.register_user("constraint_user", "user2@example.com", "password123")
        
        # Test unique email constraint  
        with pytest.raises(AuthenticationError):
            auth_manager.register_user("different_user", "user1@example.com", "password123")
        
        # Verify constraints at database level
        with sqlite3.connect(temp_db_path) as conn:
            # Try to insert duplicate username directly
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("""
                    INSERT INTO users (user_id, username, email, password_hash, salt, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("test_id", "constraint_user", "new@example.com", "hash", "salt", time.time(), True))
    
    def test_user_active_status_handling(self, auth_manager):
        """Test handling of user active status in authentication."""
        username = "status_user"
        email = "status@example.com" 
        password = "password123"
        
        # Register user
        user = auth_manager.register_user(username, email, password)
        assert user.is_active is True
        
        # Should authenticate when active
        success, auth_user = auth_manager.authenticate_user(username, password)
        assert success is True
        
        # Deactivate user directly in database
        with sqlite3.connect(auth_manager.db_path) as conn:
            conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user.user_id,))
            conn.commit()
        
        # Should not authenticate when inactive
        success, auth_user = auth_manager.authenticate_user(username, password)
        assert success is False
        assert auth_user is None


class TestUserModel:
    """Test User dataclass behavior and validation."""
    
    def test_user_model_creation_and_defaults(self):
        """Test User model creation with defaults."""
        user = User(
            user_id="test123",
            username="testuser", 
            email="test@example.com",
            password_hash="hash123",
            salt="salt123"
        )
        
        assert user.user_id == "test123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "hash123"
        assert user.salt == "salt123"
        assert user.is_active is True
        assert user.last_login is None
        assert user.created_at > 0  # Should have default timestamp
    
    def test_user_model_with_all_fields(self):
        """Test User model with all fields specified."""
        created_at = time.time()
        last_login = time.time() + 100
        
        user = User(
            user_id="full123",
            username="fulluser",
            email="full@example.com", 
            password_hash="fullhash",
            salt="fullsalt",
            created_at=created_at,
            last_login=last_login,
            is_active=False
        )
        
        assert user.created_at == created_at
        assert user.last_login == last_login
        assert user.is_active is False


class TestAuthenticationError:
    """Test AuthenticationError exception behavior."""
    
    def test_authentication_error_creation(self):
        """Test AuthenticationError can be created and raised."""
        error_message = "Test authentication error"
        
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError(error_message)
        
        assert str(exc_info.value) == error_message
        assert isinstance(exc_info.value, Exception)


# Performance and stress tests
class TestAuthenticationPerformance:
    """Performance tests for authentication operations."""
    
    @pytest.fixture
    def perf_auth_manager(self):
        """Create auth manager for performance testing."""
        return AuthenticationManager(":memory:")
    
    def test_user_registration_performance(self, perf_auth_manager):
        """Test user registration performance under load."""
        start_time = time.time()
        
        # Register 100 users
        for i in range(100):
            perf_auth_manager.register_user(f"perf_user_{i}", f"perf{i}@example.com", "password123")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete within reasonable time (less than 5 seconds)
        assert total_time < 5.0
        
        # Average time per registration should be reasonable
        avg_time = total_time / 100
        assert avg_time < 0.05  # Less than 50ms per registration
    
    def test_authentication_performance(self, perf_auth_manager):
        """Test authentication performance with multiple users."""
        # Register test users
        users = []
        for i in range(50):
            user = perf_auth_manager.register_user(f"auth_perf_{i}", f"auth{i}@example.com", "password123")
            users.append(user)
        
        # Measure authentication performance
        start_time = time.time()
        
        for user in users:
            success, auth_user = perf_auth_manager.authenticate_user(user.username, "password123")
            assert success is True
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete within reasonable time
        assert total_time < 2.0
        
        # Average authentication time should be reasonable
        avg_time = total_time / 50
        assert avg_time < 0.04  # Less than 40ms per authentication
    
    def test_session_operations_performance(self, perf_auth_manager):
        """Test session creation and validation performance."""
        # Register user
        user = perf_auth_manager.register_user("session_perf", "session@example.com", "password123")
        
        # Create multiple sessions
        start_time = time.time()
        sessions = []
        
        for _ in range(100):
            session_token = perf_auth_manager.create_session(user.user_id)
            sessions.append(session_token)
        
        creation_time = time.time() - start_time
        
        # Validate all sessions
        start_time = time.time()
        
        for session in sessions:
            is_valid, user_id = perf_auth_manager.validate_session(session)
            assert is_valid is True
            assert user_id == user.user_id
        
        validation_time = time.time() - start_time
        
        # Performance assertions
        assert creation_time < 1.0  # Less than 1 second for 100 sessions
        assert validation_time < 1.0  # Less than 1 second for 100 validations
        assert creation_time / 100 < 0.01  # Less than 10ms per session creation
        assert validation_time / 100 < 0.01  # Less than 10ms per session validation