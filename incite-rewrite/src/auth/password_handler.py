"""
Secure Password Handler Module
Provides comprehensive password hashing, verification, and security utilities.
OWASP compliant implementation with bcrypt and advanced security features.
"""

import bcrypt
import secrets
import re
import hashlib
import hmac
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import time
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PasswordStrengthLevel(Enum):
    """Password strength levels"""
    WEAK = 1
    FAIR = 2
    GOOD = 3
    STRONG = 4
    VERY_STRONG = 5

@dataclass
class PasswordPolicy:
    """Password policy configuration"""
    min_length: int = 12
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special: bool = True
    min_special_chars: int = 2
    max_repeated_chars: int = 2
    check_common_passwords: bool = True
    check_personal_info: bool = True

@dataclass
class PasswordStrengthResult:
    """Password strength analysis result"""
    strength: PasswordStrengthLevel
    score: int
    feedback: List[str]
    is_valid: bool
    entropy: float

class SecurePasswordHandler:
    """
    Secure password handler implementing OWASP guidelines.
    Provides hashing, verification, strength analysis, and security utilities.
    """
    
    def __init__(self, rounds: int = 12, policy: Optional[PasswordPolicy] = None):
        """
        Initialize password handler with bcrypt configuration.
        
        Args:
            rounds: bcrypt rounds (12-15 recommended for production)
            policy: Password policy configuration
        """
        if rounds < 10 or rounds > 20:
            raise ValueError("bcrypt rounds must be between 10 and 20")
        
        self.rounds = rounds
        self.policy = policy or PasswordPolicy()
        
        # Common passwords list (subset for demo - use full list in production)
        self._common_passwords = {
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', '123456789', 'password1', '12345678'
        }
        
        # Special characters for validation
        self._special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        # Audit logger
        self._audit_logger = logging.getLogger('password_audit')
        
    def generate_salt(self) -> bytes:
        """
        Generate cryptographically secure salt.
        
        Returns:
            32-byte salt
        """
        return bcrypt.gensalt(rounds=self.rounds)
    
    def hash_password(self, password: str, user_id: Optional[str] = None) -> str:
        """
        Hash password using bcrypt with secure salt.
        
        Args:
            password: Plain text password
            user_id: Optional user identifier for audit logging
            
        Returns:
            Base64 encoded bcrypt hash
            
        Raises:
            ValueError: If password doesn't meet policy requirements
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        # Validate password against policy
        validation_result = self.validate_password_policy(password)
        if not validation_result.is_valid:
            raise ValueError(f"Password policy violation: {', '.join(validation_result.feedback)}")
        
        try:
            # Generate salt and hash
            salt = self.generate_salt()
            password_bytes = password.encode('utf-8')
            hash_bytes = bcrypt.hashpw(password_bytes, salt)
            
            # Audit log
            self._audit_log('password_hashed', user_id, 'success')
            
            return hash_bytes.decode('utf-8')
            
        except Exception as e:
            self._audit_log('password_hash_failed', user_id, 'error', str(e))
            raise ValueError(f"Password hashing failed: {str(e)}")
    
    def verify_password(self, password: str, hashed_password: str, user_id: Optional[str] = None) -> bool:
        """
        Verify password against bcrypt hash.
        
        Args:
            password: Plain text password
            hashed_password: Bcrypt hash string
            user_id: Optional user identifier for audit logging
            
        Returns:
            True if password matches hash
        """
        if not password or not hashed_password:
            self._audit_log('password_verify_failed', user_id, 'error', 'Empty password or hash')
            return False
        
        try:
            password_bytes = password.encode('utf-8')
            hash_bytes = hashed_password.encode('utf-8')
            
            result = bcrypt.checkpw(password_bytes, hash_bytes)
            
            # Audit log
            status = 'success' if result else 'failure'
            self._audit_log('password_verified', user_id, status)
            
            return result
            
        except Exception as e:
            self._audit_log('password_verify_error', user_id, 'error', str(e))
            return False
    
    def validate_password_policy(self, password: str, user_info: Optional[Dict] = None) -> PasswordStrengthResult:
        """
        Validate password against security policy.
        
        Args:
            password: Password to validate
            user_info: Optional user information for personal info check
            
        Returns:
            PasswordStrengthResult with validation details
        """
        feedback = []
        score = 0
        
        # Length checks
        if len(password) < self.policy.min_length:
            feedback.append(f"Password must be at least {self.policy.min_length} characters long")
        else:
            score += min(20, len(password) - self.policy.min_length + 10)
        
        if len(password) > self.policy.max_length:
            feedback.append(f"Password must not exceed {self.policy.max_length} characters")
        
        # Character type requirements
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_numbers = bool(re.search(r'\d', password))
        has_special = bool(re.search(f'[{re.escape(self._special_chars)}]', password))
        
        if self.policy.require_uppercase and not has_upper:
            feedback.append("Password must contain uppercase letters")
        elif has_upper:
            score += 10
            
        if self.policy.require_lowercase and not has_lower:
            feedback.append("Password must contain lowercase letters")
        elif has_lower:
            score += 10
            
        if self.policy.require_numbers and not has_numbers:
            feedback.append("Password must contain numbers")
        elif has_numbers:
            score += 10
            
        if self.policy.require_special and not has_special:
            feedback.append("Password must contain special characters")
        elif has_special:
            score += 15
        
        # Special character count
        special_count = len([c for c in password if c in self._special_chars])
        if special_count < self.policy.min_special_chars:
            feedback.append(f"Password must contain at least {self.policy.min_special_chars} special characters")
        else:
            score += min(10, special_count * 2)
        
        # Repeated character check
        repeated_count = self._count_repeated_chars(password)
        if repeated_count > self.policy.max_repeated_chars:
            feedback.append(f"Password contains too many repeated characters (max: {self.policy.max_repeated_chars})")
            score -= 10
        
        # Common password check
        if self.policy.check_common_passwords and password.lower() in self._common_passwords:
            feedback.append("Password is too common - choose something more unique")
            score -= 20
        
        # Personal information check
        if self.policy.check_personal_info and user_info:
            if self._contains_personal_info(password, user_info):
                feedback.append("Password should not contain personal information")
                score -= 15
        
        # Calculate entropy
        entropy = self._calculate_entropy(password)
        score += min(25, int(entropy / 2))
        
        # Determine strength level
        strength = self._determine_strength(score)
        
        # Additional feedback based on strength
        if strength == PasswordStrengthLevel.WEAK:
            feedback.append("Consider using a longer, more complex password")
        elif strength == PasswordStrengthLevel.FAIR:
            feedback.append("Password could be stronger - add more character types")
        
        is_valid = len(feedback) == 0 and strength.value >= 3
        
        return PasswordStrengthResult(
            strength=strength,
            score=max(0, score),
            feedback=feedback,
            is_valid=is_valid,
            entropy=entropy
        )
    
    def generate_secure_password(self, length: int = 16, include_symbols: bool = True) -> str:
        """
        Generate cryptographically secure password.
        
        Args:
            length: Password length (minimum 12)
            include_symbols: Include special symbols
            
        Returns:
            Secure random password
        """
        if length < 12:
            raise ValueError("Password length must be at least 12 characters")
        
        # Character sets
        lowercase = 'abcdefghijklmnopqrstuvwxyz'
        uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        numbers = '0123456789'
        symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?' if include_symbols else ''
        
        # Ensure at least one character from each set
        password_chars = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(numbers)
        ]
        
        if include_symbols:
            password_chars.append(secrets.choice(symbols))
        
        # Fill remaining length with random characters from all sets
        all_chars = lowercase + uppercase + numbers + symbols
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle the password characters
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    def hash_hmac(self, message: str, secret_key: str) -> str:
        """
        Generate HMAC-SHA256 hash for message authentication.
        
        Args:
            message: Message to hash
            secret_key: Secret key for HMAC
            
        Returns:
            Hex encoded HMAC hash
        """
        return hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_hmac(self, message: str, signature: str, secret_key: str) -> bool:
        """
        Verify HMAC signature.
        
        Args:
            message: Original message
            signature: HMAC signature to verify
            secret_key: Secret key used for signing
            
        Returns:
            True if signature is valid
        """
        expected_signature = self.hash_hmac(message, secret_key)
        return hmac.compare_digest(signature, expected_signature)
    
    def _count_repeated_chars(self, password: str) -> int:
        """Count maximum consecutive repeated characters."""
        if len(password) < 2:
            return 0
        
        max_repeated = 1
        current_repeated = 1
        
        for i in range(1, len(password)):
            if password[i] == password[i-1]:
                current_repeated += 1
                max_repeated = max(max_repeated, current_repeated)
            else:
                current_repeated = 1
        
        return max_repeated - 1  # Return extra repeated chars beyond first occurrence
    
    def _contains_personal_info(self, password: str, user_info: Dict) -> bool:
        """Check if password contains personal information."""
        password_lower = password.lower()
        
        # Check common personal info fields
        personal_fields = ['username', 'email', 'first_name', 'last_name', 'name']
        
        for field in personal_fields:
            if field in user_info and user_info[field]:
                value = str(user_info[field]).lower()
                if len(value) >= 4 and value in password_lower:
                    return True
        
        return False
    
    def _calculate_entropy(self, password: str) -> float:
        """Calculate password entropy in bits."""
        charset_size = 0
        
        if re.search(r'[a-z]', password):
            charset_size += 26
        if re.search(r'[A-Z]', password):
            charset_size += 26
        if re.search(r'\d', password):
            charset_size += 10
        if re.search(f'[{re.escape(self._special_chars)}]', password):
            charset_size += len(self._special_chars)
        
        if charset_size == 0:
            return 0
        
        import math
        return len(password) * math.log2(charset_size)
    
    def _determine_strength(self, score: int) -> PasswordStrengthLevel:
        """Determine password strength based on score."""
        if score < 25:
            return PasswordStrengthLevel.WEAK
        elif score < 50:
            return PasswordStrengthLevel.FAIR
        elif score < 75:
            return PasswordStrengthLevel.GOOD
        elif score < 100:
            return PasswordStrengthLevel.STRONG
        else:
            return PasswordStrengthLevel.VERY_STRONG
    
    def _audit_log(self, action: str, user_id: Optional[str], status: str, details: str = ""):
        """Log security events for audit trail."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'user_id': user_id or 'unknown',
            'status': status,
            'details': details,
            'source_ip': '127.0.0.1'  # Would be populated from request context
        }
        
        self._audit_logger.info(f"SECURITY_AUDIT: {log_entry}")

class PasswordAttackProtection:
    """Protection against password-based attacks."""
    
    def __init__(self, max_attempts: int = 5, lockout_duration: int = 900):
        """
        Initialize attack protection.
        
        Args:
            max_attempts: Maximum failed attempts before lockout
            lockout_duration: Lockout duration in seconds
        """
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration
        self._attempts: Dict[str, List[datetime]] = {}
        self._lockouts: Dict[str, datetime] = {}
    
    def is_locked_out(self, identifier: str) -> bool:
        """Check if identifier is currently locked out."""
        if identifier in self._lockouts:
            lockout_end = self._lockouts[identifier] + timedelta(seconds=self.lockout_duration)
            if datetime.utcnow() < lockout_end:
                return True
            else:
                # Lockout expired, remove it
                del self._lockouts[identifier]
                if identifier in self._attempts:
                    del self._attempts[identifier]
        
        return False
    
    def record_failed_attempt(self, identifier: str) -> bool:
        """
        Record failed authentication attempt.
        
        Args:
            identifier: User identifier (username, email, IP)
            
        Returns:
            True if lockout was triggered
        """
        now = datetime.utcnow()
        
        # Initialize attempts list if not exists
        if identifier not in self._attempts:
            self._attempts[identifier] = []
        
        # Add current attempt
        self._attempts[identifier].append(now)
        
        # Remove attempts older than 1 hour (sliding window)
        cutoff = now - timedelta(hours=1)
        self._attempts[identifier] = [
            attempt for attempt in self._attempts[identifier]
            if attempt > cutoff
        ]
        
        # Check if lockout should be triggered
        if len(self._attempts[identifier]) >= self.max_attempts:
            self._lockouts[identifier] = now
            logger.warning(f"Account locked due to failed attempts: {identifier}")
            return True
        
        return False
    
    def reset_attempts(self, identifier: str):
        """Reset failed attempts for identifier."""
        if identifier in self._attempts:
            del self._attempts[identifier]
        if identifier in self._lockouts:
            del self._lockouts[identifier]
    
    def get_remaining_attempts(self, identifier: str) -> int:
        """Get remaining attempts before lockout."""
        if identifier not in self._attempts:
            return self.max_attempts
        
        return max(0, self.max_attempts - len(self._attempts[identifier]))