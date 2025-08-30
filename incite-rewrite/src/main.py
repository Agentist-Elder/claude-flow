import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

from .core.config import settings
from .database.connection import create_tables, close_database, check_database_connection
from .api.routes import auth, documents, text_processing
from .api.middleware.rate_limiting import init_redis, close_redis, RateLimitMiddleware
from .websocket.connection_manager import manager
from .utils.logging import setup_logging

# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
WEBSOCKET_CONNECTIONS = Counter('websocket_connections_total', 'Total WebSocket connections')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting InciteRewrite API", version=settings.APP_VERSION)
    
    try:
        # Initialize database
        await create_tables()
        
        # Check database connection
        if not await check_database_connection():
            logger.error("Database connection failed during startup")
            raise Exception("Database connection failed")
        
        # Initialize Redis for rate limiting
        await init_redis()
        
        # Start background tasks
        cleanup_task = asyncio.create_task(periodic_cleanup())
        
        logger.info("InciteRewrite API started successfully")
        
        yield
        
        # Shutdown
        logger.info("Shutting down InciteRewrite API")
        
        # Cancel background tasks
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        
        # Close connections
        await close_redis()
        await close_database()
        
        logger.info("InciteRewrite API shutdown complete")
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise


async def periodic_cleanup():
    """Background task for periodic cleanup."""
    while True:
        try:
            # Clean up inactive WebSocket connections every 5 minutes
            await asyncio.sleep(300)
            await manager.cleanup_inactive_connections(timeout_minutes=30)
            logger.debug("Periodic cleanup completed")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Periodic cleanup failed", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-ready FastAPI backend for InciteRewrite platform",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
    max_age=3600,
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Rate limiter for slowapi
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    
    return response


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add process time header and collect metrics."""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add process time header
        response.headers["X-Process-Time"] = str(process_time)
        
        # Collect Prometheus metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.observe(process_time)
        
        return response
    except Exception as e:
        # Log error and collect error metrics
        logger.error("Request processing failed", 
                    method=request.method,
                    path=request.url.path,
                    error=str(e))
        
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=500
        ).inc()
        
        raise


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning("HTTP exception", 
                  status_code=exc.status_code,
                  detail=exc.detail,
                  path=request.url.path)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Exception",
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning("Validation error", 
                  errors=exc.errors(),
                  path=request.url.path)
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Request validation failed",
            "details": exc.errors(),
            "path": request.url.path
        }
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle Starlette HTTP exceptions."""
    logger.warning("Starlette HTTP exception",
                  status_code=exc.status_code,
                  detail=exc.detail,
                  path=request.url.path)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Exception",
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error("Unhandled exception", 
                error=str(exc),
                type=type(exc).__name__,
                path=request.url.path)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "status_code": 500,
            "path": request.url.path
        }
    )


# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.APP_VERSION
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with database and Redis status."""
    db_healthy = await check_database_connection()
    
    # Check Redis connection
    redis_healthy = True
    try:
        from .api.middleware.rate_limiting import redis_client
        if redis_client:
            await redis_client.ping()
    except Exception:
        redis_healthy = False
    
    # Get connection stats
    ws_stats = manager.get_connection_count()
    
    return {
        "status": "healthy" if db_healthy and redis_healthy else "degraded",
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "services": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "websocket": "healthy"
        },
        "websocket_stats": ws_stats,
        "environment": settings.ENVIRONMENT
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    if not settings.PROMETHEUS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    return generate_latest()


# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(text_processing.router)


# WebSocket endpoint for real-time features
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket, user_id: str):
    """WebSocket endpoint for real-time communication."""
    connection_id = None
    try:
        # Connect user
        connection_id = await manager.connect(websocket, user_id)
        WEBSOCKET_CONNECTIONS.inc()
        
        # Send welcome message
        await manager.send_personal_message({
            "type": "welcome",
            "connection_id": connection_id,
            "timestamp": time.time()
        }, user_id)
        
        # Handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message = eval(data)  # In production, use json.loads with proper validation
                
                # Handle different message types
                if message.get("type") == "join_room":
                    room_id = message.get("room_id")
                    if room_id:
                        await manager.join_room(connection_id, room_id)
                
                elif message.get("type") == "leave_room":
                    room_id = message.get("room_id")
                    if room_id:
                        await manager.leave_room(connection_id, room_id)
                
                elif message.get("type") == "room_message":
                    room_id = message.get("room_id")
                    content = message.get("content")
                    if room_id and content:
                        await manager.send_to_room({
                            "type": "room_message",
                            "room_id": room_id,
                            "user_id": user_id,
                            "content": content,
                            "timestamp": time.time()
                        }, room_id)
                
                logger.debug("WebSocket message processed", 
                           user_id=user_id,
                           message_type=message.get("type"))
                
            except Exception as e:
                logger.error("WebSocket message handling failed", 
                           user_id=user_id,
                           error=str(e))
                break
    
    except Exception as e:
        logger.error("WebSocket connection failed", 
                   user_id=user_id,
                   error=str(e))
    
    finally:
        if connection_id:
            await manager.disconnect(connection_id)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs" if settings.DEBUG else "disabled",
        "health_check": "/health",
        "metrics": "/metrics" if settings.PROMETHEUS_ENABLED else "disabled"
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        server_header=False,
        date_header=False
    )