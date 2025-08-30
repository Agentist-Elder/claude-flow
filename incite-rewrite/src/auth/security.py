"""
Authentication Security Module
Comprehensive security implementation for JWT tokens, sessions, and authentication flows.
Implements OWASP security standards with advanced threat protection.
"""

import jwt
import secrets
import hashlib
import json
import time
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenType(Enum):
    """Token types for different use cases"""
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verify"
    PASSWORD_RESET = "password_reset"
    API_KEY = "api_key"

class SecurityLevel(Enum):
    """Security levels for different operations"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class SecurityConfig:
    """Security configuration settings"""
    # JWT Configuration
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    access_token_lifetime: int = 900  # 15 minutes
    refresh_token_lifetime: int = 604800  # 7 days
    
    # Session Configuration
    session_timeout: int = 3600  # 1 hour
    session_absolute_timeout: int = 28800  # 8 hours
    concurrent_sessions_limit: int = 5
    
    # Security Features
    require_mfa: bool = False
    check_ip_changes: bool = True
    log_security_events: bool = True
    encryption_key: str = secrets.token_urlsafe(32)
    
    # Rate Limiting
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15 minutes
    
    # Token Blacklisting
    enable_token_blacklist: bool = True
    blacklist_cleanup_interval: int = 3600  # 1 hour

@dataclass
class TokenClaims:
    """JWT token claims structure"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    permissions: List[str]
    session_id: str
    security_level: SecurityLevel
    issued_at: float
    expires_at: float
    token_type: TokenType
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    mfa_verified: bool = False

@dataclass
class SessionData:
    """Session data structure"""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str
    is_active: bool = True
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    mfa_verified: bool = False

class SecurityTokenManager:
    """
    Comprehensive JWT token manager with security features.
    Handles token creation, validation, refresh, and security controls.
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        """Initialize token manager with security configuration."""
        self.config = config or SecurityConfig()
        self._token_blacklist = set()
        self._session_store: Dict[str, SessionData] = {}
        self._failed_attempts: Dict[str, List[datetime]] = {}
        self._security_events = []
        
        # Initialize encryption backend
        self._backend = default_backend()
        
        # Generate RSA key pair for sensitive operations
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=self._backend
        )
        self._public_key = self._private_key.public_key()
        
        # Audit logger
        self._audit_logger = logging.getLogger('security_audit')
    
    def create_token(self, claims: TokenClaims, token_type: TokenType = TokenType.ACCESS) -> str:
        """
        Create JWT token with comprehensive security claims.
        
        Args:
            claims: Token claims data
            token_type: Type of token to create
            
        Returns:
            Signed JWT token string
        """
        try:
            # Set token-specific expiration
            now = time.time()
            if token_type == TokenType.ACCESS:
                expires_in = self.config.access_token_lifetime
            elif token_type == TokenType.REFRESH:
                expires_in = self.config.refresh_token_lifetime
            elif token_type == TokenType.EMAIL_VERIFICATION:
                expires_in = 3600  # 1 hour
            elif token_type == TokenType.PASSWORD_RESET:
                expires_in = 1800  # 30 minutes
            else:
                expires_in = self.config.access_token_lifetime
            
            claims.issued_at = now
            claims.expires_at = now + expires_in
            claims.token_type = token_type
            
            # Create JWT payload
            payload = {
                **asdict(claims),
                'iat': int(claims.issued_at),
                'exp': int(claims.expires_at),
                'jti': secrets.token_urlsafe(16),  # JWT ID for tracking
                'iss': 'incite-rewrite',  # Issuer
                'aud': 'incite-rewrite-users'  # Audience
            }
            
            # Sign token
            token = jwt.encode(
                payload,
                self.config.jwt_secret_key,
                algorithm=self.config.jwt_algorithm
            )
            
            # Log token creation
            self._log_security_event('token_created', claims.user_id, {
                'token_type': token_type.value,
                'session_id': claims.session_id,
                'security_level': claims.security_level.value
            })
            
            return token
            
        except Exception as e:
            self._log_security_event('token_creation_failed', claims.user_id, {
                'error': str(e),
                'token_type': token_type.value
            })
            raise ValueError(f"Token creation failed: {str(e)}")
    
    def validate_token(self, token: str, expected_type: Optional[TokenType] = None) -> TokenClaims:
        """
        Validate and decode JWT token with security checks.
        
        Args:
            token: JWT token string
            expected_type: Expected token type for validation
            
        Returns:
            Decoded token claims
            
        Raises:
            ValueError: If token is invalid or security checks fail
        """
        if not token:
            raise ValueError("Token is required")
        
        # Check token blacklist
        if self.config.enable_token_blacklist and self._is_token_blacklisted(token):
            raise ValueError("Token has been revoked")
        
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
                audience='incite-rewrite-users',
                issuer='incite-rewrite'
            )
            
            # Create TokenClaims object
            claims = TokenClaims(
                user_id=payload['user_id'],
                username=payload['username'],
                email=payload['email'],
                roles=payload['roles'],
                permissions=payload['permissions'],
                session_id=payload['session_id'],
                security_level=SecurityLevel(payload['security_level']),
                issued_at=payload['issued_at'],
                expires_at=payload['expires_at'],
                token_type=TokenType(payload['token_type']),
                ip_address=payload.get('ip_address'),
                user_agent=payload.get('user_agent'),
                mfa_verified=payload.get('mfa_verified', False)
            )
            
            # Validate token type if specified
            if expected_type and claims.token_type != expected_type:
                raise ValueError(f"Expected {expected_type.value} token, got {claims.token_type.value}")
            
            # Check session validity
            if not self._is_session_valid(claims.session_id):
                raise ValueError("Session is no longer valid")
            
            # Log successful validation
            self._log_security_event('token_validated', claims.user_id, {
                'token_type': claims.token_type.value,
                'session_id': claims.session_id
            })
            
            return claims
            
        except jwt.ExpiredSignatureError:
            self._log_security_event('token_expired', 'unknown', {'token_prefix': token[:10]})
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            self._log_security_event('token_invalid', 'unknown', {
                'error': str(e),
                'token_prefix': token[:10]
            })
            raise ValueError(f"Invalid token: {str(e)}")
    
    def refresh_token(self, refresh_token: str, new_ip: Optional[str] = None) -> Tuple[str, str]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            new_ip: New IP address for security checking
            
        Returns:
            Tuple of (new_access_token, new_refresh_token)
        """
        # Validate refresh token
        claims = self.validate_token(refresh_token, TokenType.REFRESH)
        
        # Security check: IP address change
        if self.config.check_ip_changes and new_ip and claims.ip_address != new_ip:
            self._log_security_event('token_refresh_ip_change', claims.user_id, {
                'old_ip': claims.ip_address,
                'new_ip': new_ip,
                'session_id': claims.session_id
            })
            # Could require re-authentication here for high security environments
        
        # Create new tokens
        new_claims = TokenClaims(
            user_id=claims.user_id,
            username=claims.username,
            email=claims.email,
            roles=claims.roles,
            permissions=claims.permissions,
            session_id=claims.session_id,
            security_level=claims.security_level,
            issued_at=time.time(),
            expires_at=0,  # Will be set in create_token
            token_type=TokenType.ACCESS,
            ip_address=new_ip or claims.ip_address,
            user_agent=claims.user_agent,
            mfa_verified=claims.mfa_verified
        )
        
        # Generate new tokens
        new_access_token = self.create_token(new_claims, TokenType.ACCESS)
        new_refresh_token = self.create_token(new_claims, TokenType.REFRESH)
        
        # Blacklist old refresh token
        if self.config.enable_token_blacklist:
            self._blacklist_token(refresh_token)
        
        # Update session activity
        self._update_session_activity(claims.session_id)
        
        return new_access_token, new_refresh_token
    
    def revoke_token(self, token: str, user_id: Optional[str] = None):
        """
        Revoke token by adding to blacklist.
        
        Args:
            token: Token to revoke
            user_id: User ID for audit logging
        """
        if self.config.enable_token_blacklist:
            self._blacklist_token(token)
            self._log_security_event('token_revoked', user_id or 'unknown', {
                'token_prefix': token[:10]
            })
    
    def revoke_all_user_tokens(self, user_id: str):
        """
        Revoke all tokens for a specific user.
        
        Args:
            user_id: User ID to revoke tokens for
        """
        # Invalidate all sessions for user
        sessions_to_remove = []
        for session_id, session_data in self._session_store.items():
            if session_data.user_id == user_id:
                session_data.is_active = False
                sessions_to_remove.append(session_id)
        
        # Remove inactive sessions
        for session_id in sessions_to_remove:
            del self._session_store[session_id]
        
        self._log_security_event('all_tokens_revoked', user_id, {
            'sessions_revoked': len(sessions_to_remove)
        })
    
    def create_session(self, user_id: str, ip_address: str, user_agent: str, 
                      security_level: SecurityLevel = SecurityLevel.MEDIUM) -> str:
        """
        Create new user session.
        
        Args:
            user_id: User identifier
            ip_address: Client IP address
            user_agent: Client user agent
            security_level: Security level for session
            
        Returns:
            Session ID
        """
        # Check concurrent session limit
        active_sessions = [
            s for s in self._session_store.values()
            if s.user_id == user_id and s.is_active
        ]
        
        if len(active_sessions) >= self.config.concurrent_sessions_limit:
            # Remove oldest session
            oldest_session = min(active_sessions, key=lambda s: s.last_activity)
            oldest_session.is_active = False
            self._log_security_event('session_limit_exceeded', user_id, {
                'removed_session': oldest_session.session_id
            })
        
        # Create new session
        session_id = secrets.token_urlsafe(32)
        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
            security_level=security_level
        )
        
        self._session_store[session_id] = session_data
        
        self._log_security_event('session_created', user_id, {
            'session_id': session_id,
            'ip_address': ip_address,
            'security_level': security_level.value
        })
        
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[SessionData]:
        """
        Validate and return session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionData if valid, None otherwise
        """
        session = self._session_store.get(session_id)
        
        if not session or not session.is_active:
            return None
        
        # Check session timeout
        now = datetime.utcnow()
        time_since_activity = (now - session.last_activity).total_seconds()
        time_since_creation = (now - session.created_at).total_seconds()
        
        if time_since_activity > self.config.session_timeout:
            session.is_active = False
            self._log_security_event('session_timeout', session.user_id, {
                'session_id': session_id,
                'inactive_duration': time_since_activity
            })
            return None
        
        if time_since_creation > self.config.session_absolute_timeout:
            session.is_active = False
            self._log_security_event('session_absolute_timeout', session.user_id, {
                'session_id': session_id,
                'total_duration': time_since_creation
            })
            return None
        
        return session
    
    def encrypt_sensitive_data(self, data: str, context: Optional[str] = None) -> str:
        """
        Encrypt sensitive data using AES-256-GCM.
        
        Args:
            data: Data to encrypt
            context: Optional context for additional security
            
        Returns:
            Base64 encoded encrypted data with IV
        """
        try:
            # Generate random IV
            iv = secrets.token_bytes(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.config.encryption_key.encode()[:32]),
                modes.GCM(iv),
                backend=self._backend
            )
            
            encryptor = cipher.encryptor()
            
            # Add context as associated data if provided
            if context:
                encryptor.authenticate_additional_data(context.encode())
            
            # Encrypt data
            ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
            
            # Combine IV + tag + ciphertext
            encrypted_data = iv + encryptor.tag + ciphertext
            
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise ValueError(f"Encryption failed: {str(e)}")
    
    def decrypt_sensitive_data(self, encrypted_data: str, context: Optional[str] = None) -> str:
        """
        Decrypt sensitive data using AES-256-GCM.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            context: Optional context for verification
            
        Returns:
            Decrypted data string
        """
        try:
            # Decode base64
            data = base64.b64decode(encrypted_data.encode())
            
            # Extract components
            iv = data[:16]
            tag = data[16:32]
            ciphertext = data[32:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.config.encryption_key.encode()[:32]),
                modes.GCM(iv, tag),
                backend=self._backend
            )
            
            decryptor = cipher.decryptor()
            
            # Add context as associated data if provided
            if context:
                decryptor.authenticate_additional_data(context.encode())
            
            # Decrypt data
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise ValueError(f"Decryption failed: {str(e)}")
    
    def generate_csrf_token(self, session_id: str) -> str:
        """
        Generate CSRF token for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            CSRF token
        """
        # Create CSRF token with session binding
        csrf_data = {
            'session_id': session_id,
            'timestamp': time.time(),
            'random': secrets.token_urlsafe(16)
        }
        
        csrf_string = json.dumps(csrf_data, sort_keys=True)
        
        # Sign with HMAC
        import hmac
        signature = hmac.new(
            self.config.jwt_secret_key.encode(),
            csrf_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return base64.b64encode(f"{csrf_string}.{signature}".encode()).decode()
    
    def validate_csrf_token(self, csrf_token: str, session_id: str) -> bool:
        """
        Validate CSRF token for session.
        
        Args:
            csrf_token: CSRF token to validate
            session_id: Expected session ID
            
        Returns:
            True if token is valid
        """
        try:
            # Decode token
            decoded = base64.b64decode(csrf_token.encode()).decode()
            csrf_string, signature = decoded.rsplit('.', 1)
            
            # Verify signature
            import hmac
            expected_signature = hmac.new(
                self.config.jwt_secret_key.encode(),
                csrf_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return False
            
            # Verify session and timestamp
            csrf_data = json.loads(csrf_string)
            
            if csrf_data['session_id'] != session_id:
                return False
            
            # Check token age (valid for 1 hour)
            token_age = time.time() - csrf_data['timestamp']
            if token_age > 3600:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is in blacklist."""
        return token in self._token_blacklist
    
    def _blacklist_token(self, token: str):
        """Add token to blacklist."""
        self._token_blacklist.add(token)
    
    def _is_session_valid(self, session_id: str) -> bool:
        """Check if session is valid."""
        return self.validate_session(session_id) is not None
    
    def _update_session_activity(self, session_id: str):
        """Update session last activity timestamp."""
        session = self._session_store.get(session_id)
        if session:
            session.last_activity = datetime.utcnow()
    
    def _log_security_event(self, event_type: str, user_id: str, details: Dict[str, Any]):
        """Log security event for audit trail."""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'details': details,
            'source': 'SecurityTokenManager'
        }
        
        self._security_events.append(event)
        
        if self.config.log_security_events:
            self._audit_logger.info(f"SECURITY_EVENT: {event}")
    
    def cleanup_expired_tokens(self):
        """Clean up expired tokens and sessions."""
        now = datetime.utcnow()
        
        # Clean up expired sessions
        expired_sessions = []
        for session_id, session in self._session_store.items():
            if not session.is_active:
                expired_sessions.append(session_id)
            else:
                # Check timeouts
                time_since_activity = (now - session.last_activity).total_seconds()
                time_since_creation = (now - session.created_at).total_seconds()
                
                if (time_since_activity > self.config.session_timeout or 
                    time_since_creation > self.config.session_absolute_timeout):
                    session.is_active = False
                    expired_sessions.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_sessions:
            del self._session_store[session_id]
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")