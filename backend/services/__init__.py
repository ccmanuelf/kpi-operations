"""
KPI Operations Services Package
Orchestration layer between routes and domain calculations.

Phase 2: Service Layer Enforcement
Services coordinate CRUD operations with business logic:
- KPI calculations
- Workflow state machines
- Hold/resume workflows
- Client assignment logic
"""

# KPI Calculation Services
from backend.services.production_kpi_service import ProductionKPIService
from backend.services.quality_kpi_service import QualityKPIService
from backend.services.analytics_service import AnalyticsService

# Business Logic Services (Phase 2)
from backend.services.production_service import ProductionService, get_production_service
from backend.services.quality_service import QualityService, get_quality_service
from backend.services.work_order_service import WorkOrderService, get_work_order_service
from backend.services.hold_service import HoldService, get_hold_service
from backend.services.employee_service import EmployeeService, get_employee_service
from backend.services.attendance_service import AttendanceService, get_attendance_service
from backend.services.downtime_service import DowntimeService, get_downtime_service

__all__ = [
    # KPI Services
    "ProductionKPIService",
    "QualityKPIService",
    "AnalyticsService",
    # Business Logic Services
    "ProductionService",
    "QualityService",
    "WorkOrderService",
    "HoldService",
    "EmployeeService",
    "AttendanceService",
    "DowntimeService",
    # Dependency Injection Factories
    "get_production_service",
    "get_quality_service",
    "get_work_order_service",
    "get_hold_service",
    "get_employee_service",
    "get_attendance_service",
    "get_downtime_service",
]
