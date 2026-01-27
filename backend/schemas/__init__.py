"""
SQLAlchemy ORM schemas for database tables
Complete multi-tenant implementation with all 14 tables
"""
# Core multi-tenant foundation
from .client import Client, ClientType
from .user import User, UserRole
from .employee import Employee
from .floating_pool import FloatingPool

# Work order management
from .work_order import WorkOrder, WorkOrderStatus
from .job import Job
from .part_opportunities import PartOpportunities

# Phase 1: Production tracking
from .product import Product
from .shift import Shift
from .production_entry import ProductionEntry

# Phase 2: WIP & Downtime
from .hold_entry import HoldEntry, HoldStatus
from .downtime_entry import DowntimeEntry

# Phase 3: Attendance
from .attendance_entry import AttendanceEntry, AbsenceType
from .coverage_entry import CoverageEntry

# Phase 4: Quality
from .quality_entry import QualityEntry
from .defect_detail import DefectDetail, DefectType

# Phase 9: Client-specific Defect Type Catalog
from .defect_type_catalog import DefectTypeCatalog

# Phase 6: User Preferences
from .user_preferences import UserPreferences, DashboardWidgetDefaults

# Phase 10: Workflow Foundation
from .workflow import WorkflowTransitionLog

__all__ = [
    # Core foundation
    "Client",
    "ClientType",
    "User",
    "UserRole",
    "Employee",
    "FloatingPool",
    # Work orders
    "WorkOrder",
    "WorkOrderStatus",
    "Job",
    "PartOpportunities",
    # Phase 1
    "Product",
    "Shift",
    "ProductionEntry",
    # Phase 2
    "HoldEntry",
    "HoldStatus",
    "DowntimeEntry",
    # Phase 3
    "AttendanceEntry",
    "AbsenceType",
    "CoverageEntry",
    # Phase 4
    "QualityEntry",
    "DefectDetail",
    "DefectType",
    # Phase 9
    "DefectTypeCatalog",
    # Phase 6
    "UserPreferences",
    "DashboardWidgetDefaults",
    # Phase 10
    "WorkflowTransitionLog",
]
