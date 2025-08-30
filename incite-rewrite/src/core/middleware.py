"""
Security Middleware Module
Comprehensive middleware implementation for API security, CORS, rate limiting,
and request validation. Implements OWASP security guidelines.
"""

import time
import json
import re
import logging
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
from urllib.parse import urlparse
import hashlib
import hmac
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityHeaderType(Enum):
    """Security header types"""
    HSTS = "Strict-Transport-Security"
    CSP = "Content-Security-Policy"
    X_FRAME_OPTIONS = "X-Frame-Options"
    X_CONTENT_TYPE_OPTIONS = "X-Content-Type-Options"
    X_XSS_PROTECTION = "X-XSS-Protection"
    REFERRER_POLICY = "Referrer-Policy"
    PERMISSIONS_POLICY = "Permissions-Policy"

class RateLimitType(Enum):
    """Rate limiting types"""
    PER_IP = "per_ip"
    PER_USER = "per_user"
    PER_ENDPOINT = "per_endpoint"
    GLOBAL = "global"

@dataclass
class CORSConfig:
    """CORS configuration"""
    allowed_origins: List[str]
    allowed_methods: List[str]
    allowed_headers: List[str]
    allow_credentials: bool
    max_age: int
    expose_headers: List[str]

@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10
    enable_adaptive: bool = True

@dataclass
class SecurityConfig:
    """Security middleware configuration"""
    # CORS settings
    cors_config: CORSConfig
    
    # Rate limiting
    rate_limit_config: RateLimitConfig
    
    # Security headers
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000  # 1 year
    csp_policy: str = "default-src 'self'"
    
    # Request validation
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    max_json_depth: int = 20
    allowed_content_types: Set[str] = None
    
    # SQL injection protection
    enable_sql_injection_detection: bool = True
    sql_patterns: List[str] = None
    
    # XSS protection
    enable_xss_protection: bool = True
    xss_patterns: List[str] = None
    
    # IP filtering
    blocked_ips: Set[str] = None
    allowed_ips: Set[str] = None
    
    # Logging
    log_security_events: bool = True
    log_all_requests: bool = False

class RequestValidator:
    """Request validation and sanitization"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        
        # SQL injection patterns
        self.sql_patterns = config.sql_patterns or [
            r"(?i)(union\s+select)",
            r"(?i)(select\s+.*\s+from)",
            r"(?i)(drop\s+table)",
            r"(?i)(delete\s+from)",
            r"(?i)(update\s+.*\s+set)",
            r"(?i)(insert\s+into)",
            r"(?i)(exec\s*\()",
            r"(?i)(script\s*:)",
            r"(?i)('.*or.*'.*=.*')",
            r"(?i)(\".*or.*\".*=.*\")",
            r"(?i)(;.*--)",
            r"(?i)(/\*.*\*/)",
        ]
        
        # XSS patterns
        self.xss_patterns = config.xss_patterns or [
            r"(?i)(<script[^>]*>.*?</script>)",
            r"(?i)(<iframe[^>]*>.*?</iframe>)",
            r"(?i)(javascript:)",
            r"(?i)(on\w+\s*=)",
            r"(?i)(<img[^>]*src\s*=\s*['\"]javascript:)",
            r"(?i)(<object[^>]*>.*?</object>)",
            r"(?i)(<embed[^>]*>)",
            r"(?i)(expression\s*\()",
            r"(?i)(vbscript:)",
            r"(?i)(@import)",
        ]
        
        # Compile regex patterns
        self.compiled_sql_patterns = [re.compile(pattern) for pattern in self.sql_patterns]
        self.compiled_xss_patterns = [re.compile(pattern) for pattern in self.xss_patterns]
        
        # Allowed content types
        self.allowed_content_types = config.allowed_content_types or {
            'application/json',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
            'text/plain'
        }
    
    def validate_request_size(self, content_length: Optional[int]) -> bool:
        """Validate request content length"""
        if content_length is None:
            return True
        return content_length <= self.config.max_request_size
    
    def validate_content_type(self, content_type: Optional[str]) -> bool:
        """Validate request content type"""
        if not content_type:
            return True
        
        # Extract base content type (ignore charset, boundary, etc.)
        base_type = content_type.split(';')[0].strip().lower()
        return base_type in self.allowed_content_types
    
    def detect_sql_injection(self, data: Any) -> List[str]:
        """Detect potential SQL injection attempts"""
        if not self.config.enable_sql_injection_detection:
            return []
        
        detected_patterns = []
        
        # Convert data to string for pattern matching
        if isinstance(data, dict):
            text_data = json.dumps(data, default=str)
        elif isinstance(data, list):
            text_data = json.dumps(data, default=str)
        else:
            text_data = str(data)
        
        # Check against SQL injection patterns
        for i, pattern in enumerate(self.compiled_sql_patterns):
            if pattern.search(text_data):
                detected_patterns.append(self.sql_patterns[i])
        
        return detected_patterns
    
    def detect_xss_attempts(self, data: Any) -> List[str]:
        """Detect potential XSS attempts"""
        if not self.config.enable_xss_protection:
            return []
        
        detected_patterns = []
        
        # Convert data to string for pattern matching
        if isinstance(data, dict):
            text_data = json.dumps(data, default=str)
        elif isinstance(data, list):
            text_data = json.dumps(data, default=str)
        else:
            text_data = str(data)
        
        # Check against XSS patterns
        for i, pattern in enumerate(self.compiled_xss_patterns):
            if pattern.search(text_data):
                detected_patterns.append(self.xss_patterns[i])
        
        return detected_patterns
    
    def sanitize_input(self, data: Any) -> Any:
        """Sanitize input data"""
        if isinstance(data, dict):
            return {key: self.sanitize_input(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_input(item) for item in data]
        elif isinstance(data, str):
            # Basic HTML entity encoding
            return (data.replace('&', '&amp;')
                       .replace('<', '&lt;')
                       .replace('>', '&gt;')
                       .replace('"', '&quot;')
                       .replace("'", '&#x27;'))
        else:
            return data
    
    def validate_json_depth(self, data: Any, current_depth: int = 0) -> bool:
        """Validate JSON nesting depth to prevent DoS attacks"""
        if current_depth > self.config.max_json_depth:
            return False
        
        if isinstance(data, dict):
            return all(self.validate_json_depth(value, current_depth + 1) 
                      for value in data.values())
        elif isinstance(data, list):
            return all(self.validate_json_depth(item, current_depth + 1) 
                      for item in data)
        else:
            return True

class RateLimiter:
    """Advanced rate limiting with multiple strategies"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        
        # Rate limiting stores
        self._minute_store: Dict[str, deque] = defaultdict(deque)
        self._hour_store: Dict[str, deque] = defaultdict(deque)
        self._day_store: Dict[str, deque] = defaultdict(deque)
        
        # Adaptive rate limiting
        self._burst_store: Dict[str, List[float]] = defaultdict(list)
        self._penalty_store: Dict[str, float] = defaultdict(float)
        
        # Cleanup timestamps
        self._last_cleanup = time.time()
    
    def is_allowed(self, identifier: str, weight: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed under rate limits.
        
        Args:
            identifier: Rate limit identifier (IP, user ID, etc.)
            weight: Request weight (default 1)
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        now = time.time()
        
        # Cleanup old entries periodically
        if now - self._last_cleanup > 60:  # Cleanup every minute
            self._cleanup_old_entries(now)
            self._last_cleanup = now
        
        # Check current rates
        minute_count = self._get_current_count(identifier, now, 60, self._minute_store)
        hour_count = self._get_current_count(identifier, now, 3600, self._hour_store)
        day_count = self._get_current_count(identifier, now, 86400, self._day_store)
        
        # Check burst protection
        if self.config.enable_adaptive:
            burst_allowed = self._check_burst_limit(identifier, now)
            if not burst_allowed:
                return False, {
                    'reason': 'burst_limit_exceeded',
                    'retry_after': 60,
                    'current_minute': minute_count,
                    'limit_minute': self.config.requests_per_minute
                }
        
        # Apply penalties for previous violations
        penalty_factor = self._get_penalty_factor(identifier)
        effective_minute_limit = max(1, int(self.config.requests_per_minute / penalty_factor))
        effective_hour_limit = max(1, int(self.config.requests_per_hour / penalty_factor))
        
        # Check limits
        if minute_count + weight > effective_minute_limit:
            self._apply_penalty(identifier)
            return False, {
                'reason': 'minute_limit_exceeded',
                'retry_after': 60 - (now % 60),
                'current_minute': minute_count,
                'limit_minute': effective_minute_limit
            }
        
        if hour_count + weight > effective_hour_limit:
            self._apply_penalty(identifier)
            return False, {
                'reason': 'hour_limit_exceeded',
                'retry_after': 3600 - (now % 3600),
                'current_hour': hour_count,
                'limit_hour': effective_hour_limit
            }
        
        if day_count + weight > self.config.requests_per_day:
            return False, {
                'reason': 'day_limit_exceeded',
                'retry_after': 86400 - (now % 86400),
                'current_day': day_count,
                'limit_day': self.config.requests_per_day
            }
        
        # Record request
        for _ in range(weight):
            self._minute_store[identifier].append(now)
            self._hour_store[identifier].append(now)
            self._day_store[identifier].append(now)
        
        # Record for burst detection
        if self.config.enable_adaptive:
            self._burst_store[identifier].append(now)
        
        return True, {
            'allowed': True,
            'current_minute': minute_count + weight,
            'current_hour': hour_count + weight,
            'current_day': day_count + weight,
            'limit_minute': effective_minute_limit,
            'limit_hour': effective_hour_limit,
            'limit_day': self.config.requests_per_day
        }
    
    def _get_current_count(self, identifier: str, now: float, window: int, store: Dict[str, deque]) -> int:
        """Get current request count within time window"""
        cutoff = now - window
        queue = store[identifier]
        
        # Remove old entries
        while queue and queue[0] < cutoff:
            queue.popleft()
        
        return len(queue)
    
    def _check_burst_limit(self, identifier: str, now: float) -> bool:
        """Check burst protection limits"""
        burst_window = 10  # 10 second burst window
        cutoff = now - burst_window
        
        # Clean old burst records
        burst_records = self._burst_store[identifier]
        self._burst_store[identifier] = [t for t in burst_records if t > cutoff]
        
        return len(self._burst_store[identifier]) < self.config.burst_limit
    
    def _get_penalty_factor(self, identifier: str) -> float:
        """Get current penalty factor for identifier"""
        penalty = self._penalty_store.get(identifier, 0)
        
        # Decay penalty over time (1% per minute)
        now = time.time()
        decay_rate = 0.01 / 60  # per second
        decayed_penalty = max(0, penalty - decay_rate * (now - getattr(self, f'_penalty_time_{identifier}', now)))
        
        self._penalty_store[identifier] = decayed_penalty
        setattr(self, f'_penalty_time_{identifier}', now)
        
        return max(1, 1 + decayed_penalty)
    
    def _apply_penalty(self, identifier: str):
        """Apply penalty for rate limit violation"""
        current_penalty = self._penalty_store.get(identifier, 0)
        self._penalty_store[identifier] = min(10, current_penalty + 0.5)  # Max 10x penalty
        setattr(self, f'_penalty_time_{identifier}', time.time())
    
    def _cleanup_old_entries(self, now: float):
        """Clean up old rate limiting entries"""
        # Clean minute store
        for identifier in list(self._minute_store.keys()):
            cutoff = now - 60
            queue = self._minute_store[identifier]
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                del self._minute_store[identifier]
        
        # Clean hour store
        for identifier in list(self._hour_store.keys()):
            cutoff = now - 3600
            queue = self._hour_store[identifier]
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                del self._hour_store[identifier]
        
        # Clean day store
        for identifier in list(self._day_store.keys()):
            cutoff = now - 86400
            queue = self._day_store[identifier]
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                del self._day_store[identifier]
        
        # Clean burst store
        for identifier in list(self._burst_store.keys()):
            cutoff = now - 10
            self._burst_store[identifier] = [t for t in self._burst_store[identifier] if t > cutoff]
            if not self._burst_store[identifier]:
                del self._burst_store[identifier]

class SecurityMiddleware:
    """
    Comprehensive security middleware for web applications.
    Implements OWASP security guidelines and best practices.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.validator = RequestValidator(config)
        self.rate_limiter = RateLimiter(config.rate_limit_config)
        
        # Security event logger
        self._security_logger = logging.getLogger('security_middleware')
        
        # Blocked IPs
        self.blocked_ips = config.blocked_ips or set()
        self.allowed_ips = config.allowed_ips or set()
        
        # Request tracking
        self._request_count = 0
        self._security_events = []
    
    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming request through security pipeline.
        
        Args:
            request_data: Request information including headers, body, IP, etc.
            
        Returns:
            Processing result with security information
        """
        result = {
            'allowed': True,
            'security_events': [],
            'headers_to_add': {},
            'modifications': {}
        }
        
        try:
            # Extract request information
            ip_address = request_data.get('ip_address', 'unknown')
            method = request_data.get('method', 'GET')
            path = request_data.get('path', '/')
            headers = request_data.get('headers', {})
            body = request_data.get('body')
            user_id = request_data.get('user_id')
            
            # 1. IP filtering
            if not self._check_ip_allowed(ip_address):
                result['allowed'] = False
                result['reason'] = 'ip_blocked'
                self._log_security_event('ip_blocked', ip_address, {'path': path})
                return result
            
            # 2. Rate limiting
            rate_limit_id = user_id if user_id else ip_address
            rate_allowed, rate_info = self.rate_limiter.is_allowed(rate_limit_id)
            
            if not rate_allowed:
                result['allowed'] = False
                result['reason'] = 'rate_limit_exceeded'
                result['rate_limit_info'] = rate_info
                self._log_security_event('rate_limit_exceeded', ip_address, rate_info)
                return result
            
            result['rate_limit_info'] = rate_info
            
            # 3. Request validation
            content_length = headers.get('content-length')
            if content_length:
                try:
                    content_length = int(content_length)
                except ValueError:
                    content_length = None
            
            if not self.validator.validate_request_size(content_length):
                result['allowed'] = False
                result['reason'] = 'request_too_large'
                self._log_security_event('request_too_large', ip_address, {'size': content_length})
                return result
            
            # 4. Content type validation
            content_type = headers.get('content-type')
            if not self.validator.validate_content_type(content_type):
                result['allowed'] = False
                result['reason'] = 'invalid_content_type'
                self._log_security_event('invalid_content_type', ip_address, {'content_type': content_type})
                return result
            
            # 5. Body validation and sanitization
            if body:
                # SQL injection detection
                sql_patterns = self.validator.detect_sql_injection(body)
                if sql_patterns:
                    result['security_events'].append({
                        'type': 'sql_injection_attempt',
                        'patterns': sql_patterns
                    })
                    self._log_security_event('sql_injection_attempt', ip_address, {
                        'path': path,
                        'patterns': sql_patterns
                    })
                    
                    # For high security, block the request
                    result['allowed'] = False
                    result['reason'] = 'sql_injection_detected'
                    return result
                
                # XSS detection
                xss_patterns = self.validator.detect_xss_attempts(body)
                if xss_patterns:
                    result['security_events'].append({
                        'type': 'xss_attempt',
                        'patterns': xss_patterns
                    })
                    self._log_security_event('xss_attempt', ip_address, {
                        'path': path,
                        'patterns': xss_patterns
                    })
                
                # JSON depth validation
                if isinstance(body, (dict, list)):
                    if not self.validator.validate_json_depth(body):
                        result['allowed'] = False
                        result['reason'] = 'json_too_deep'
                        self._log_security_event('json_too_deep', ip_address, {'path': path})
                        return result
                
                # Sanitize input if needed
                if result['security_events']:
                    result['modifications']['sanitized_body'] = self.validator.sanitize_input(body)
            
            # 6. CORS handling
            origin = headers.get('origin')
            if origin:
                cors_headers = self._handle_cors(origin, method, headers)
                result['headers_to_add'].update(cors_headers)
            
            # 7. Security headers
            if self.config.enable_security_headers:
                security_headers = self._get_security_headers()
                result['headers_to_add'].update(security_headers)
            
            # 8. Log request if configured
            if self.config.log_all_requests:
                self._log_request(ip_address, method, path, headers)
            
            self._request_count += 1
            
        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            result['allowed'] = False
            result['reason'] = 'security_error'
            result['error'] = str(e)
        
        return result
    
    def _check_ip_allowed(self, ip_address: str) -> bool:
        """Check if IP address is allowed"""
        # If allowlist is configured, only allow listed IPs
        if self.allowed_ips:
            return ip_address in self.allowed_ips
        
        # Otherwise, check blocklist
        return ip_address not in self.blocked_ips
    
    def _handle_cors(self, origin: str, method: str, headers: Dict[str, str]) -> Dict[str, str]:
        """Handle CORS preflight and actual requests"""
        cors_headers = {}
        
        # Check if origin is allowed
        cors_config = self.config.cors_config
        origin_allowed = False
        
        for allowed_origin in cors_config.allowed_origins:
            if allowed_origin == "*" or allowed_origin == origin:
                origin_allowed = True
                break
            # Support wildcard subdomains
            if allowed_origin.startswith("*."):
                domain = allowed_origin[2:]
                if origin.endswith(domain):
                    origin_allowed = True
                    break
        
        if origin_allowed:
            cors_headers['Access-Control-Allow-Origin'] = origin
            
            if cors_config.allow_credentials:
                cors_headers['Access-Control-Allow-Credentials'] = 'true'
            
            if method == 'OPTIONS':
                # Preflight request
                cors_headers['Access-Control-Allow-Methods'] = ', '.join(cors_config.allowed_methods)
                cors_headers['Access-Control-Allow-Headers'] = ', '.join(cors_config.allowed_headers)
                cors_headers['Access-Control-Max-Age'] = str(cors_config.max_age)
            
            if cors_config.expose_headers:
                cors_headers['Access-Control-Expose-Headers'] = ', '.join(cors_config.expose_headers)
        
        return cors_headers
    
    def _get_security_headers(self) -> Dict[str, str]:
        """Get security headers to add to response"""
        headers = {}
        
        # HSTS
        headers[SecurityHeaderType.HSTS.value] = f"max-age={self.config.hsts_max_age}; includeSubDomains"
        
        # CSP
        headers[SecurityHeaderType.CSP.value] = self.config.csp_policy
        
        # X-Frame-Options
        headers[SecurityHeaderType.X_FRAME_OPTIONS.value] = "DENY"
        
        # X-Content-Type-Options
        headers[SecurityHeaderType.X_CONTENT_TYPE_OPTIONS.value] = "nosniff"
        
        # X-XSS-Protection
        headers[SecurityHeaderType.X_XSS_PROTECTION.value] = "1; mode=block"
        
        # Referrer Policy
        headers[SecurityHeaderType.REFERRER_POLICY.value] = "strict-origin-when-cross-origin"
        
        # Permissions Policy
        headers[SecurityHeaderType.PERMISSIONS_POLICY.value] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )
        
        return headers
    
    def _log_security_event(self, event_type: str, ip_address: str, details: Dict[str, Any]):
        """Log security event"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'ip_address': ip_address,
            'details': details,
            'request_count': self._request_count
        }
        
        self._security_events.append(event)
        
        if self.config.log_security_events:
            self._security_logger.warning(f"SECURITY_EVENT: {event}")
    
    def _log_request(self, ip_address: str, method: str, path: str, headers: Dict[str, str]):
        """Log request details"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'ip_address': ip_address,
            'method': method,
            'path': path,
            'user_agent': headers.get('user-agent', 'unknown'),
            'request_id': self._request_count
        }
        
        logger.info(f"REQUEST: {log_data}")
    
    def get_security_report(self) -> Dict[str, Any]:
        """Get security report with statistics"""
        return {
            'total_requests': self._request_count,
            'security_events': len(self._security_events),
            'recent_events': self._security_events[-10:],  # Last 10 events
            'blocked_ips_count': len(self.blocked_ips),
            'rate_limit_stats': {
                'active_limiters': len(self.rate_limiter._minute_store),
                'penalties_active': len(self.rate_limiter._penalty_store)
            }
        }