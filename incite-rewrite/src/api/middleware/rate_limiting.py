import asyncio
import time
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis.asyncio as redis
import structlog
from ...core.config import settings

logger = structlog.get_logger(__name__)

# Redis connection for rate limiting
redis_client: Optional[redis.Redis] = None


async def init_redis():
    """Initialize Redis connection for rate limiting."""
    global redis_client
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connection established for rate limiting")
    except Exception as e:
        logger.error("Failed to connect to Redis for rate limiting", error=str(e))
        redis_client = None


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


class AsyncRateLimiter:
    """Async rate limiter with Redis backend."""
    
    def __init__(self):
        self.default_limits = {
            "per_minute": settings.RATE_LIMIT_REQUESTS // 60,
            "per_hour": settings.RATE_LIMIT_REQUESTS,
            "per_day": settings.RATE_LIMIT_REQUESTS * 24
        }
    
    async def is_allowed(
        self, 
        key: str, 
        limit: int, 
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed based on rate limits.
        
        Args:
            key: Rate limit key (usually IP or user ID)
            limit: Maximum requests allowed
            window: Time window in seconds
            cost: Cost of this request (default 1)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        if not redis_client:
            # Fallback: always allow if Redis is not available
            logger.warning("Redis not available, rate limiting disabled")
            return True, {"remaining": limit, "reset": int(time.time()) + window}
        
        try:
            current_time = int(time.time())
            window_start = current_time - window
            
            # Use Redis sorted set for sliding window
            pipe = redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {f"{current_time}:{asyncio.current_task()}": current_time})
            
            # Set expiration
            pipe.expire(key, window)
            
            results = await pipe.execute()
            current_count = results[1] + cost  # Include current request
            
            is_allowed = current_count <= limit
            remaining = max(0, limit - current_count)
            reset_time = current_time + window
            
            if not is_allowed:
                # Remove the request we just added since it's not allowed
                await redis_client.zrem(key, f"{current_time}:{asyncio.current_task()}")
            
            return is_allowed, {
                "remaining": remaining,
                "reset": reset_time,
                "limit": limit,
                "window": window
            }
            
        except Exception as e:
            logger.error("Rate limiting check failed", key=key, error=str(e))
            # Fallback: allow request if Redis fails
            return True, {"remaining": limit, "reset": int(time.time()) + window}


# Global rate limiter instance
rate_limiter = AsyncRateLimiter()


def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Rate limit key
    """
    # Try to get user ID from JWT token
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            # Extract user ID from token (simplified)
            # In production, you'd properly decode the JWT
            token = auth_header[7:]  # Remove "Bearer "
            # For now, use a hash of the token as user identifier
            import hashlib
            user_hash = hashlib.md5(token.encode()).hexdigest()[:8]
            return f"user:{user_hash}"
        except Exception:
            pass
    
    # Fallback to IP address
    client_ip = get_remote_address(request)
    return f"ip:{client_ip}"


class RateLimitMiddleware:
    """Rate limiting middleware."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        # Skip rate limiting for health checks and static files
        if (request.url.path.startswith("/health") or 
            request.url.path.startswith("/static") or
            request.url.path.startswith("/docs") or
            request.url.path.startswith("/openapi.json")):
            await self.app(scope, receive, send)
            return
        
        # Get rate limit key
        key = get_rate_limit_key(request)
        
        # Different limits for different endpoints
        if request.url.path.startswith("/api/text-processing"):
            # Lower limit for AI processing endpoints
            limit = 10  # 10 requests per hour
            window = 3600
            cost = 5  # Higher cost for AI operations
        elif request.url.path.startswith("/api/auth"):
            # Standard limit for auth endpoints
            limit = 30  # 30 requests per hour
            window = 3600
            cost = 1
        else:
            # Default limits
            limit = settings.RATE_LIMIT_REQUESTS
            window = settings.RATE_LIMIT_WINDOW
            cost = 1
        
        # Check rate limit
        is_allowed, rate_info = await rate_limiter.is_allowed(
            f"rate_limit:{key}:{request.url.path}", 
            limit, 
            window,
            cost
        )
        
        if not is_allowed:
            logger.warning("Rate limit exceeded", 
                          key=key, 
                          path=request.url.path,
                          limit=limit)
            
            response_content = {
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {limit} per {window} seconds",
                "retry_after": rate_info["reset"] - int(time.time())
            }
            
            response = HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=response_content
            )
            
            # Send rate limit exceeded response
            response_obj = response.__dict__
            await send({
                "type": "http.response.start",
                "status": response.status_code,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"x-ratelimit-limit", str(limit).encode()],
                    [b"x-ratelimit-remaining", str(rate_info["remaining"]).encode()],
                    [b"x-ratelimit-reset", str(rate_info["reset"]).encode()],
                    [b"retry-after", str(rate_info["reset"] - int(time.time())).encode()],
                ]
            })
            await send({
                "type": "http.response.body",
                "body": str(response_content).encode()
            })
            return
        
        # Add rate limit headers to response
        async def add_rate_limit_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    [b"x-ratelimit-limit", str(limit).encode()],
                    [b"x-ratelimit-remaining", str(rate_info["remaining"]).encode()],
                    [b"x-ratelimit-reset", str(rate_info["reset"]).encode()],
                ])
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, add_rate_limit_headers)


# Slowapi limiter for simpler rate limiting
def get_client_ip(request: Request):
    """Get client IP for slowapi rate limiting."""
    return get_remote_address(request)


# Create slowapi limiter instance
limiter = Limiter(key_func=get_client_ip)
rate_limit_exceeded_handler = _rate_limit_exceeded_handler


# Rate limit decorators for different endpoint types
def auth_rate_limit():
    """Rate limit for authentication endpoints."""
    return limiter.limit("30/hour")


def api_rate_limit():
    """Rate limit for general API endpoints.""" 
    return limiter.limit("100/hour")


def processing_rate_limit():
    """Rate limit for text processing endpoints."""
    return limiter.limit("10/hour")


def upload_rate_limit():
    """Rate limit for upload endpoints."""
    return limiter.limit("20/hour")