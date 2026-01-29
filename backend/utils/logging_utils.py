"""
Centralized Logging Utilities
=============================
Provides structured logging for backend operations with consistent formatting.

Usage:
    from backend.utils.logging_utils import get_module_logger, log_operation, log_error

    logger = get_module_logger(__name__)
    log_operation(logger, "CREATE", "attendance", user_id="admin", client_id="CLT001")
"""
import logging
import functools
from typing import Optional, Any, Dict, Callable
from datetime import datetime


def get_module_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module with consistent configuration.

    Args:
        name: Module name (__name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only add handler if not already configured
    if not logger.handlers and not logging.root.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def log_operation(
    logger: logging.Logger,
    operation: str,
    resource: str,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    client_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    level: str = "INFO"
) -> None:
    """
    Log a data operation with structured format.

    Args:
        logger: Logger instance
        operation: Operation type (CREATE, READ, UPDATE, DELETE, QUERY)
        resource: Resource type (attendance, production, quality, etc.)
        resource_id: ID of the affected resource
        user_id: User performing the operation
        client_id: Client context
        details: Additional details to log
        level: Log level (INFO, WARNING, ERROR, DEBUG)
    """
    parts = [f"[{operation}] {resource}"]

    if resource_id:
        parts.append(f"id={resource_id}")
    if user_id:
        parts.append(f"user={user_id}")
    if client_id:
        parts.append(f"client={client_id}")
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        parts.append(f"({detail_str})")

    message = " | ".join(parts)

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message)


def log_error(
    logger: logging.Logger,
    operation: str,
    resource: str,
    error: Exception,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    client_id: Optional[str] = None
) -> None:
    """
    Log an error during an operation.

    Args:
        logger: Logger instance
        operation: Operation that failed
        resource: Resource type
        error: Exception that occurred
        resource_id: ID of affected resource
        user_id: User who triggered the operation
        client_id: Client context
    """
    parts = [f"[{operation}_ERROR] {resource}"]

    if resource_id:
        parts.append(f"id={resource_id}")
    if user_id:
        parts.append(f"user={user_id}")
    if client_id:
        parts.append(f"client={client_id}")

    parts.append(f"error={type(error).__name__}: {str(error)}")

    message = " | ".join(parts)
    logger.error(message, exc_info=True)


def log_security_event(
    logger: logging.Logger,
    event_type: str,
    user_id: Optional[str] = None,
    client_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None
) -> None:
    """
    Log a security-related event.

    Args:
        logger: Logger instance
        event_type: Type of security event (AUTH_FAILURE, ACCESS_DENIED, etc.)
        user_id: User involved
        client_id: Client context
        ip_address: Request IP address
        details: Additional details
    """
    parts = [f"[SECURITY] {event_type}"]

    if user_id:
        parts.append(f"user={user_id}")
    if client_id:
        parts.append(f"client={client_id}")
    if ip_address:
        parts.append(f"ip={ip_address}")
    if details:
        parts.append(f"details={details}")

    message = " | ".join(parts)
    logger.warning(message)


def log_performance(
    logger: logging.Logger,
    operation: str,
    duration_ms: float,
    resource: Optional[str] = None,
    record_count: Optional[int] = None
) -> None:
    """
    Log performance metrics for an operation.

    Args:
        logger: Logger instance
        operation: Operation performed
        duration_ms: Duration in milliseconds
        resource: Resource type
        record_count: Number of records processed
    """
    parts = [f"[PERF] {operation}"]

    if resource:
        parts.append(f"resource={resource}")

    parts.append(f"duration={duration_ms:.2f}ms")

    if record_count is not None:
        parts.append(f"records={record_count}")

    message = " | ".join(parts)

    # Log as warning if slow (> 1000ms)
    if duration_ms > 1000:
        logger.warning(message)
    else:
        logger.debug(message)


def with_logging(
    operation: str,
    resource: str,
    id_param: Optional[str] = None
) -> Callable:
    """
    Decorator to add logging to route handlers.

    Args:
        operation: Operation type
        resource: Resource type
        id_param: Parameter name containing resource ID

    Usage:
        @with_logging("CREATE", "attendance")
        def create_attendance(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_module_logger(func.__module__)

            # Extract user_id and client_id if available
            user_id = None
            client_id = None
            resource_id = None

            current_user = kwargs.get('current_user')
            if current_user and hasattr(current_user, 'user_id'):
                user_id = current_user.user_id
            if current_user and hasattr(current_user, 'client_id'):
                client_id = current_user.client_id

            if id_param and id_param in kwargs:
                resource_id = kwargs[id_param]

            start_time = datetime.now()

            try:
                result = func(*args, **kwargs)

                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                log_operation(
                    logger, operation, resource,
                    resource_id=resource_id,
                    user_id=user_id,
                    client_id=client_id,
                    details={"duration_ms": f"{duration_ms:.2f}"}
                )

                return result

            except Exception as e:
                log_error(
                    logger, operation, resource, e,
                    resource_id=resource_id,
                    user_id=user_id,
                    client_id=client_id
                )
                raise

        return wrapper
    return decorator
