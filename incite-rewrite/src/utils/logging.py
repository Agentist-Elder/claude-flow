import sys
import logging
from typing import Any, Dict, Optional
import structlog
from pythonjsonlogger import jsonlogger
from ..core.config import settings


def setup_logging():
    """Configure structured logging for the application."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL)
    )
    
    # Disable noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.LOG_FORMAT.lower() == "json":
        # JSON formatting for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable formatting for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class RequestLoggingMiddleware:
    """Middleware to log HTTP requests and responses."""
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger(__name__)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request info
        method = scope["method"]
        path = scope["path"]
        query_string = scope.get("query_string", b"").decode()
        client = scope.get("client", ("unknown", 0))
        
        # Log request
        self.logger.info(
            "Request received",
            method=method,
            path=path,
            query_string=query_string,
            client_ip=client[0],
            client_port=client[1]
        )
        
        # Process request
        await self.app(scope, receive, send)


class DatabaseLoggingMixin:
    """Mixin class for database operation logging."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def log_query(self, operation: str, table: str, **kwargs):
        """Log database query."""
        self.logger.debug(
            "Database operation",
            operation=operation,
            table=table,
            **kwargs
        )
    
    def log_error(self, operation: str, error: Exception, **kwargs):
        """Log database error."""
        self.logger.error(
            "Database operation failed",
            operation=operation,
            error=str(error),
            error_type=type(error).__name__,
            **kwargs
        )


def log_api_call(
    operation: str,
    endpoint: str,
    user_id: Optional[str] = None,
    duration: Optional[float] = None,
    status_code: Optional[int] = None,
    **kwargs
):
    """Log API call with standard format."""
    logger = get_logger("api")
    
    log_data = {
        "operation": operation,
        "endpoint": endpoint,
        "user_id": user_id,
        "duration": duration,
        "status_code": status_code,
        **kwargs
    }
    
    if status_code and status_code >= 400:
        logger.error("API call failed", **log_data)
    else:
        logger.info("API call completed", **log_data)


def log_authentication_event(
    event_type: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    success: bool = True,
    reason: Optional[str] = None,
    **kwargs
):
    """Log authentication events."""
    logger = get_logger("auth")
    
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "email": email,
        "success": success,
        "reason": reason,
        **kwargs
    }
    
    if success:
        logger.info("Authentication event", **log_data)
    else:
        logger.warning("Authentication failed", **log_data)


def log_processing_event(
    job_type: str,
    document_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: str = "started",
    duration: Optional[float] = None,
    error: Optional[str] = None,
    **kwargs
):
    """Log text processing events."""
    logger = get_logger("processing")
    
    log_data = {
        "job_type": job_type,
        "document_id": document_id,
        "user_id": user_id,
        "status": status,
        "duration": duration,
        "error": error,
        **kwargs
    }
    
    if error:
        logger.error("Processing failed", **log_data)
    elif status == "completed":
        logger.info("Processing completed", **log_data)
    else:
        logger.debug("Processing event", **log_data)


def log_websocket_event(
    event_type: str,
    user_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    room_id: Optional[str] = None,
    **kwargs
):
    """Log WebSocket events."""
    logger = get_logger("websocket")
    
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "connection_id": connection_id,
        "room_id": room_id,
        **kwargs
    }
    
    logger.info("WebSocket event", **log_data)


def log_security_event(
    event_type: str,
    severity: str = "info",
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """Log security-related events."""
    logger = get_logger("security")
    
    log_data = {
        "event_type": event_type,
        "severity": severity,
        "user_id": user_id,
        "ip_address": ip_address,
        "details": details,
        **kwargs
    }
    
    if severity in ["critical", "high"]:
        logger.critical("Security event", **log_data)
    elif severity == "medium":
        logger.warning("Security event", **log_data)
    else:
        logger.info("Security event", **log_data)


def log_performance_metric(
    metric_name: str,
    value: float,
    unit: str = "seconds",
    context: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """Log performance metrics."""
    logger = get_logger("performance")
    
    log_data = {
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "context": context,
        **kwargs
    }
    
    logger.info("Performance metric", **log_data)


# Context manager for operation logging
class LoggedOperation:
    """Context manager for logging operations with timing."""
    
    def __init__(
        self,
        operation: str,
        logger_name: str = "operations",
        level: str = "info",
        **context
    ):
        self.operation = operation
        self.logger = get_logger(logger_name)
        self.level = level
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        
        getattr(self.logger, self.level)(
            f"{self.operation} started",
            operation=self.operation,
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        
        if exc_type is None:
            getattr(self.logger, self.level)(
                f"{self.operation} completed",
                operation=self.operation,
                duration=duration,
                **self.context
            )
        else:
            self.logger.error(
                f"{self.operation} failed",
                operation=self.operation,
                duration=duration,
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.context
            )