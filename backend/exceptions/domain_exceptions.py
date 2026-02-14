"""
Domain Exception Definitions
Standardized exceptions for domain-level errors.
"""

from typing import Optional, Dict, Any


class DomainException(Exception):
    """Base exception for domain errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ValidationError(DomainException):
    """Raised when domain validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)
        self.field = field


class CalculationError(DomainException):
    """Raised when a calculation cannot be performed."""

    def __init__(self, message: str, metric: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CALCULATION_ERROR", details=details)
        self.metric = metric


class ResourceNotFoundError(DomainException):
    """Raised when a required resource is not found."""

    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(message, code="RESOURCE_NOT_FOUND", details=details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class MultiTenantViolationError(DomainException):
    """Raised when a multi-tenant isolation rule is violated."""

    def __init__(
        self, message: str = "Access denied to resource from different tenant", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code="TENANT_VIOLATION", details=details)


class CapacityPlanningError(DomainException):
    """Raised for capacity planning specific errors."""

    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CAPACITY_ERROR", details=details)
        self.operation = operation


class BOMExplosionError(CapacityPlanningError):
    """Raised when BOM explosion fails."""

    def __init__(self, message: str, parent_item: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, operation="bom_explosion", details=details)
        self.parent_item = parent_item


class SchedulingError(CapacityPlanningError):
    """Raised when scheduling operation fails."""

    def __init__(self, message: str, order_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, operation="scheduling", details=details)
        self.order_id = order_id
