"""
Input Validation and Security Utilities
Comprehensive validation functions for securing user inputs and preventing common attacks.
Implements OWASP validation guidelines with extensive security checks.
"""

import re
import email.utils
import ipaddress
import urllib.parse
import hashlib
import hmac
import base64
import json
import html
from typing import Any, Dict, List, Optional, Union, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationType(Enum):
    """Validation types for different data formats"""
    EMAIL = "email"
    USERNAME = "username"
    PASSWORD = "password"
    URL = "url"
    IP_ADDRESS = "ip_address"
    PHONE = "phone"
    UUID = "uuid"
    JSON = "json"
    SQL_SAFE = "sql_safe"
    HTML_SAFE = "html_safe"
    FILENAME = "filename"
    PATH = "path"

class ValidationSeverity(Enum):
    """Validation error severity levels"""
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

@dataclass
class ValidationRule:
    """Validation rule configuration"""
    rule_type: ValidationType
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_values: Optional[Set[str]] = None
    custom_validator: Optional[callable] = None

@dataclass
class ValidationResult:
    """Validation result with detailed feedback"""
    is_valid: bool
    cleaned_value: Any = None
    errors: List[str] = None
    warnings: List[str] = None
    severity: ValidationSeverity = ValidationSeverity.INFO
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

class SecurityValidator:
    """
    Comprehensive security validator for input sanitization and validation.
    Implements OWASP guidelines for secure input handling.
    """
    
    def __init__(self):
        # Common patterns for validation
        self.patterns = {
            'email': re.compile(
                r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            ),
            'username': re.compile(
                r'^[a-zA-Z0-9_.-]{3,50}$'
            ),
            'uuid': re.compile(
                r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
                re.IGNORECASE
            ),
            'filename': re.compile(
                r'^[a-zA-Z0-9._-]+$'
            ),
            'safe_path': re.compile(
                r'^[a-zA-Z0-9._/-]+$'
            ),
            'phone': re.compile(
                r'^\+?1?\d{9,15}$'
            )
        }
        
        # Dangerous patterns to detect
        self.danger_patterns = {
            'sql_injection': [
                re.compile(r"(?i)(union\s+select)", re.IGNORECASE),
                re.compile(r"(?i)(select\s+.*\s+from)", re.IGNORECASE),
                re.compile(r"(?i)(drop\s+table)", re.IGNORECASE),
                re.compile(r"(?i)(delete\s+from)", re.IGNORECASE),
                re.compile(r"(?i)(insert\s+into)", re.IGNORECASE),
                re.compile(r"(?i)(update\s+.*\s+set)", re.IGNORECASE),
                re.compile(r"(?i)('.*or.*'.*=.*')", re.IGNORECASE),
                re.compile(r"(?i)(\".*or.*\".*=.*\")", re.IGNORECASE),
                re.compile(r"(?i)(;.*--)", re.IGNORECASE),
                re.compile(r"(?i)(/\*.*\*/)", re.IGNORECASE),
            ],
            'xss': [
                re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
                re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
                re.compile(r"javascript:", re.IGNORECASE),
                re.compile(r"on\w+\s*=", re.IGNORECASE),
                re.compile(r"<img[^>]*src\s*=\s*['\"]javascript:", re.IGNORECASE),
                re.compile(r"<object[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL),
                re.compile(r"<embed[^>]*>", re.IGNORECASE),
                re.compile(r"expression\s*\(", re.IGNORECASE),
                re.compile(r"vbscript:", re.IGNORECASE),
                re.compile(r"@import", re.IGNORECASE),
            ],
            'path_traversal': [
                re.compile(r"\.\./"),
                re.compile(r"\.\.\\\"),
                re.compile(r"%2e%2e%2f", re.IGNORECASE),
                re.compile(r"%2e%2e%5c", re.IGNORECASE),
            ],
            'command_injection': [
                re.compile(r";.*rm\s", re.IGNORECASE),
                re.compile(r";\s*cat\s", re.IGNORECASE),
                re.compile(r";\s*ls\s", re.IGNORECASE),
                re.compile(r";\s*chmod\s", re.IGNORECASE),
                re.compile(r"\|\s*rm\s", re.IGNORECASE),
                re.compile(r"&&\s*rm\s", re.IGNORECASE),
                re.compile(r"`.*`"),
                re.compile(r"\$\(.*\)"),
            ]
        }
        
        # File extension whitelist
        self.safe_extensions = {
            'images': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'},
            'documents': {'.pdf', '.doc', '.docx', '.txt', '.rtf'},
            'archives': {'.zip', '.tar', '.gz'},
            'code': {'.py', '.js', '.html', '.css', '.json', '.xml'}
        }
        
        # Maximum sizes for different data types
        self.max_sizes = {
            'text': 10000,  # 10KB for text fields
            'email': 254,   # RFC 5321 limit
            'username': 50,
            'password': 128,
            'filename': 255,
            'path': 4096,
            'url': 2048
        }
    
    def validate_email(self, email_str: str, strict: bool = True) -> ValidationResult:
        """
        Validate email address with comprehensive security checks.
        
        Args:
            email_str: Email address to validate
            strict: Enable strict validation mode
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=False)
        
        if not email_str:
            result.errors.append("Email address is required")
            return result
        
        # Length check
        if len(email_str) > self.max_sizes['email']:
            result.errors.append(f"Email address too long (max {self.max_sizes['email']} characters)")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Basic format validation
        if not self.patterns['email'].match(email_str):
            result.errors.append("Invalid email format")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Security checks
        security_issues = self._check_security_patterns(email_str)
        if security_issues:
            result.errors.extend([f"Security issue detected: {issue}" for issue in security_issues])
            result.severity = ValidationSeverity.CRITICAL
            return result
        
        # RFC 5322 validation using email.utils
        try:
            parsed = email.utils.parseaddr(email_str)
            if not parsed[1] or '@' not in parsed[1]:
                result.errors.append("Invalid email format (RFC validation failed)")
                result.severity = ValidationSeverity.ERROR
                return result
        except Exception:
            result.errors.append("Email parsing failed")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Strict mode additional checks
        if strict:
            local, domain = email_str.split('@', 1)
            
            # Local part checks
            if len(local) > 64:
                result.errors.append("Email local part too long (max 64 characters)")
                result.severity = ValidationSeverity.ERROR
                return result
            
            # Domain checks
            if not self._validate_domain(domain):
                result.errors.append("Invalid email domain")
                result.severity = ValidationSeverity.ERROR
                return result
        
        result.is_valid = True
        result.cleaned_value = email_str.lower().strip()
        return result
    
    def validate_username(self, username: str) -> ValidationResult:
        """
        Validate username with security considerations.
        
        Args:
            username: Username to validate
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=False)
        
        if not username:
            result.errors.append("Username is required")
            return result
        
        # Length checks
        if len(username) < 3:
            result.errors.append("Username must be at least 3 characters long")
            result.severity = ValidationSeverity.ERROR
            return result
        
        if len(username) > self.max_sizes['username']:
            result.errors.append(f"Username too long (max {self.max_sizes['username']} characters)")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Pattern validation
        if not self.patterns['username'].match(username):
            result.errors.append("Username can only contain letters, numbers, dots, underscores, and hyphens")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Security checks
        security_issues = self._check_security_patterns(username)
        if security_issues:
            result.errors.extend([f"Security issue detected: {issue}" for issue in security_issues])
            result.severity = ValidationSeverity.CRITICAL
            return result
        
        # Reserved usernames check
        reserved_usernames = {
            'admin', 'root', 'administrator', 'system', 'null', 'undefined',
            'api', 'www', 'mail', 'ftp', 'support', 'help', 'security'
        }
        
        if username.lower() in reserved_usernames:
            result.warnings.append("Username is reserved - consider choosing another")
            result.severity = ValidationSeverity.WARNING
        
        result.is_valid = True
        result.cleaned_value = username.strip()
        return result
    
    def validate_url(self, url: str, allowed_schemes: Optional[Set[str]] = None) -> ValidationResult:
        """
        Validate URL with security checks for malicious URLs.
        
        Args:
            url: URL to validate
            allowed_schemes: Set of allowed URL schemes (default: http, https)
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=False)
        
        if not url:
            result.errors.append("URL is required")
            return result
        
        # Length check
        if len(url) > self.max_sizes['url']:
            result.errors.append(f"URL too long (max {self.max_sizes['url']} characters)")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Security checks
        security_issues = self._check_security_patterns(url)
        if security_issues:
            result.errors.extend([f"Security issue detected: {issue}" for issue in security_issues])
            result.severity = ValidationSeverity.CRITICAL
            return result
        
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Scheme validation
            if allowed_schemes is None:
                allowed_schemes = {'http', 'https'}
            
            if parsed.scheme not in allowed_schemes:
                result.errors.append(f"URL scheme must be one of: {', '.join(allowed_schemes)}")
                result.severity = ValidationSeverity.ERROR
                return result
            
            # Hostname validation
            if not parsed.netloc:
                result.errors.append("URL must have a valid hostname")
                result.severity = ValidationSeverity.ERROR
                return result
            
            # Check for localhost/private IPs in production
            if self._is_private_or_local_url(parsed.netloc):
                result.warnings.append("URL points to private/local address")
                result.severity = ValidationSeverity.WARNING
            
            # Check for suspicious paths
            if self._has_suspicious_path(parsed.path):
                result.warnings.append("URL path contains potentially suspicious elements")
                result.severity = ValidationSeverity.WARNING
            
        except Exception as e:
            result.errors.append(f"URL parsing failed: {str(e)}")
            result.severity = ValidationSeverity.ERROR
            return result
        
        result.is_valid = True
        result.cleaned_value = url.strip()
        return result
    
    def validate_ip_address(self, ip_str: str, version: Optional[int] = None) -> ValidationResult:
        """
        Validate IP address (IPv4 or IPv6).
        
        Args:
            ip_str: IP address string to validate
            version: IP version (4 or 6) - None for either
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=False)
        
        if not ip_str:
            result.errors.append("IP address is required")
            return result
        
        try:
            ip = ipaddress.ip_address(ip_str.strip())
            
            # Version check if specified
            if version and ip.version != version:
                result.errors.append(f"Expected IPv{version} address, got IPv{ip.version}")
                result.severity = ValidationSeverity.ERROR
                return result
            
            # Security warnings for special addresses
            if ip.is_private:
                result.warnings.append("IP address is in private range")
                result.severity = ValidationSeverity.WARNING
            
            if ip.is_loopback:
                result.warnings.append("IP address is loopback")
                result.severity = ValidationSeverity.WARNING
            
            if ip.is_multicast:
                result.warnings.append("IP address is multicast")
                result.severity = ValidationSeverity.WARNING
            
            result.is_valid = True
            result.cleaned_value = str(ip)
            
        except ValueError as e:
            result.errors.append(f"Invalid IP address: {str(e)}")
            result.severity = ValidationSeverity.ERROR
        
        return result
    
    def validate_filename(self, filename: str, allowed_extensions: Optional[Set[str]] = None) -> ValidationResult:
        """
        Validate filename for security and format compliance.
        
        Args:
            filename: Filename to validate
            allowed_extensions: Set of allowed file extensions
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=False)
        
        if not filename:
            result.errors.append("Filename is required")
            return result
        
        # Length check
        if len(filename) > self.max_sizes['filename']:
            result.errors.append(f"Filename too long (max {self.max_sizes['filename']} characters)")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Security checks
        security_issues = self._check_security_patterns(filename)
        if security_issues:
            result.errors.extend([f"Security issue detected: {issue}" for issue in security_issues])
            result.severity = ValidationSeverity.CRITICAL
            return result
        
        # Path traversal check
        if '../' in filename or '..\\' in filename:
            result.errors.append("Filename contains path traversal characters")
            result.severity = ValidationSeverity.CRITICAL
            return result
        
        # Pattern validation (basic safe characters)
        if not self.patterns['filename'].match(filename):
            result.errors.append("Filename contains invalid characters")
            result.severity = ValidationSeverity.ERROR
            return result
        
        # Extension validation
        if '.' in filename:
            extension = '.' + filename.split('.')[-1].lower()
            
            if allowed_extensions and extension not in allowed_extensions:
                result.errors.append(f"File extension not allowed. Allowed: {', '.join(allowed_extensions)}")
                result.severity = ValidationSeverity.ERROR
                return result
            
            # Check against dangerous extensions
            dangerous_extensions = {
                '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
                '.jar', '.php', '.asp', '.aspx', '.jsp', '.sh', '.ps1'
            }
            
            if extension in dangerous_extensions:
                result.errors.append("Potentially dangerous file extension")
                result.severity = ValidationSeverity.CRITICAL
                return result
        
        # Special filename checks (Windows reserved names)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
            'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3',
            'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        
        name_without_ext = filename.split('.')[0].upper()
        if name_without_ext in reserved_names:
            result.warnings.append("Filename is reserved on Windows systems")
            result.severity = ValidationSeverity.WARNING
        
        result.is_valid = True
        result.cleaned_value = filename.strip()
        return result
    
    def validate_json(self, json_str: str, max_depth: int = 10, max_size: int = 1048576) -> ValidationResult:
        """
        Validate JSON string with security constraints.
        
        Args:
            json_str: JSON string to validate
            max_depth: Maximum nesting depth
            max_size: Maximum JSON size in bytes
            
        Returns:
            ValidationResult with parsed JSON or errors
        """
        result = ValidationResult(is_valid=False)
        
        if not json_str:
            result.errors.append("JSON string is required")
            return result
        
        # Size check
        if len(json_str.encode('utf-8')) > max_size:
            result.errors.append(f"JSON too large (max {max_size} bytes)")
            result.severity = ValidationSeverity.ERROR
            return result
        
        try:
            # Parse JSON
            parsed_json = json.loads(json_str)
            
            # Check nesting depth
            if self._get_json_depth(parsed_json) > max_depth:
                result.errors.append(f"JSON nesting too deep (max {max_depth} levels)")
                result.severity = ValidationSeverity.ERROR
                return result
            
            # Security checks on JSON content
            json_content = json.dumps(parsed_json, default=str)
            security_issues = self._check_security_patterns(json_content)
            if security_issues:
                result.warnings.extend([f"Potential security issue: {issue}" for issue in security_issues])
                result.severity = ValidationSeverity.WARNING
            
            result.is_valid = True
            result.cleaned_value = parsed_json
            
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid JSON format: {str(e)}")
            result.severity = ValidationSeverity.ERROR
        except Exception as e:
            result.errors.append(f"JSON validation failed: {str(e)}")
            result.severity = ValidationSeverity.ERROR
        
        return result
    
    def sanitize_html(self, html_str: str, allowed_tags: Optional[Set[str]] = None) -> str:
        """
        Sanitize HTML string by removing dangerous elements.
        
        Args:
            html_str: HTML string to sanitize
            allowed_tags: Set of allowed HTML tags
            
        Returns:
            Sanitized HTML string
        """
        if not html_str:
            return ""
        
        # Basic HTML entity encoding
        sanitized = html.escape(html_str)
        
        # If allowed tags specified, implement whitelist filtering
        if allowed_tags:
            # Simple implementation - in production, use a proper HTML sanitizer like bleach
            allowed_pattern = '|'.join(re.escape(tag) for tag in allowed_tags)
            # This is a simplified example - use proper HTML parsing in production
            sanitized = re.sub(r'&lt;(?!(/?(?:' + allowed_pattern + r')\b))([^&]*)&gt;', r'&lt;\2&gt;', sanitized)
        
        return sanitized
    
    def validate_batch(self, data: Dict[str, Any], rules: Dict[str, ValidationRule]) -> Dict[str, ValidationResult]:
        """
        Validate multiple fields using specified rules.
        
        Args:
            data: Dictionary of field names and values
            rules: Dictionary of field names and validation rules
            
        Returns:
            Dictionary of field names and validation results
        """
        results = {}
        
        for field_name, rule in rules.items():
            value = data.get(field_name)
            
            # Check if field is required
            if rule.required and (value is None or value == ""):
                result = ValidationResult(is_valid=False)
                result.errors.append(f"{field_name} is required")
                result.severity = ValidationSeverity.ERROR
                results[field_name] = result
                continue
            
            # Skip validation if not required and empty
            if not rule.required and (value is None or value == ""):
                results[field_name] = ValidationResult(is_valid=True, cleaned_value=value)
                continue
            
            # Apply validation based on rule type
            if rule.rule_type == ValidationType.EMAIL:
                result = self.validate_email(str(value))
            elif rule.rule_type == ValidationType.USERNAME:
                result = self.validate_username(str(value))
            elif rule.rule_type == ValidationType.URL:
                result = self.validate_url(str(value))
            elif rule.rule_type == ValidationType.IP_ADDRESS:
                result = self.validate_ip_address(str(value))
            elif rule.rule_type == ValidationType.FILENAME:
                result = self.validate_filename(str(value))
            elif rule.rule_type == ValidationType.JSON:
                result = self.validate_json(str(value))
            else:
                # Generic validation
                result = self._validate_generic(value, rule)
            
            results[field_name] = result
        
        return results
    
    def _validate_generic(self, value: Any, rule: ValidationRule) -> ValidationResult:
        """Generic validation for custom rules."""
        result = ValidationResult(is_valid=True, cleaned_value=value)
        
        str_value = str(value)
        
        # Length checks
        if rule.min_length and len(str_value) < rule.min_length:
            result.is_valid = False
            result.errors.append(f"Value must be at least {rule.min_length} characters long")
            result.severity = ValidationSeverity.ERROR
        
        if rule.max_length and len(str_value) > rule.max_length:
            result.is_valid = False
            result.errors.append(f"Value must not exceed {rule.max_length} characters")
            result.severity = ValidationSeverity.ERROR
        
        # Pattern validation
        if rule.pattern and not re.match(rule.pattern, str_value):
            result.is_valid = False
            result.errors.append("Value does not match required pattern")
            result.severity = ValidationSeverity.ERROR
        
        # Allowed values check
        if rule.allowed_values and str_value not in rule.allowed_values:
            result.is_valid = False
            result.errors.append(f"Value must be one of: {', '.join(rule.allowed_values)}")
            result.severity = ValidationSeverity.ERROR
        
        # Custom validator
        if rule.custom_validator:
            try:
                custom_result = rule.custom_validator(value)
                if not custom_result:
                    result.is_valid = False
                    result.errors.append("Custom validation failed")
                    result.severity = ValidationSeverity.ERROR
            except Exception as e:
                result.is_valid = False
                result.errors.append(f"Custom validation error: {str(e)}")
                result.severity = ValidationSeverity.ERROR
        
        return result
    
    def _check_security_patterns(self, text: str) -> List[str]:
        """Check text against security threat patterns."""
        issues = []
        
        for threat_type, patterns in self.danger_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    issues.append(threat_type)
                    break  # Only report each threat type once
        
        return issues
    
    def _validate_domain(self, domain: str) -> bool:
        """Validate email domain."""
        if not domain or len(domain) > 255:
            return False
        
        # Basic domain pattern
        domain_pattern = re.compile(
            r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        )
        
        return domain_pattern.match(domain) is not None
    
    def _is_private_or_local_url(self, netloc: str) -> bool:
        """Check if URL points to private or local address."""
        try:
            hostname = netloc.split(':')[0]  # Remove port if present
            
            # Check for localhost variants
            local_hosts = {'localhost', '127.0.0.1', '::1', '0.0.0.0'}
            if hostname.lower() in local_hosts:
                return True
            
            # Check for private IP ranges
            try:
                ip = ipaddress.ip_address(hostname)
                return ip.is_private or ip.is_loopback
            except ValueError:
                # Not an IP address, check for local domain patterns
                return hostname.endswith('.local') or hostname.endswith('.localhost')
                
        except Exception:
            return False
    
    def _has_suspicious_path(self, path: str) -> bool:
        """Check if URL path contains suspicious elements."""
        suspicious_patterns = [
            '../', '..\\', '%2e%2e%2f', '%2e%2e%5c',
            'admin', 'config', 'backup', '.env', 'password'
        ]
        
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in suspicious_patterns)
    
    def _get_json_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of JSON object."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_json_depth(value, current_depth + 1) for value in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_json_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

class CSRFProtection:
    """CSRF token generation and validation"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        timestamp = str(int(datetime.now().timestamp()))
        message = f"{session_id}:{timestamp}"
        
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        token_data = f"{message}:{signature}"
        return base64.b64encode(token_data.encode()).decode()
    
    def validate_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Validate CSRF token."""
        try:
            token_data = base64.b64decode(token.encode()).decode()
            parts = token_data.split(':')
            
            if len(parts) != 3:
                return False
            
            token_session_id, timestamp, signature = parts
            
            # Check session ID match
            if token_session_id != session_id:
                return False
            
            # Check token age
            token_time = int(timestamp)
            current_time = int(datetime.now().timestamp())
            if current_time - token_time > max_age:
                return False
            
            # Verify signature
            message = f"{token_session_id}:{timestamp}"
            expected_signature = hmac.new(
                self.secret_key,
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception:
            return False