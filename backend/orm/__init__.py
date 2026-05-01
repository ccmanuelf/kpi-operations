"""
SQLAlchemy ORM models for database tables
Complete multi-tenant implementation with all tables

IMPORTANT: Every ORM model file in this package MUST be imported here
so that Base.metadata.create_all() discovers all tables. Failure to
import a model here was the root cause of 503 errors on fresh installs
(2026-02-23 schema-ORM mismatch incident).
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
from .coverage import ShiftCoverage

# Phase 4: Quality
from .quality_entry import QualityEntry
from .defect_detail import DefectDetail, DefectType

# Phase 7.2: Client-Level Configuration Overrides
from .client_config import ClientConfig, OTDMode

# Phase 3: Domain Events Infrastructure
from .event_store import EventStore

# Import Log (CSV/batch import auditing)
from .import_log import ImportLog

# KPI Thresholds
from .kpi_threshold import KPIThreshold

# Phase 2.1: Data Layer Normalization — junction tables
from .user_client_assignment import UserClientAssignment
from .employee_client_assignment import EmployeeClientAssignment, AssignmentType

# Phase 9: Client-specific Defect Type Catalog
from .defect_type_catalog import DefectTypeCatalog

# Task 0.5: Client-configurable Hold Catalogs
from .hold_status_catalog import HoldStatusCatalog
from .hold_reason_catalog import HoldReasonCatalog

# Sprint 1: Break Times
from .break_time import BreakTime

# Sprint 2: Production Line Topology
from .production_line import ProductionLine
from .equipment import Equipment
from .employee_line_assignment import EmployeeLineAssignment

# Phase 6: User Preferences
from .user_preferences import UserPreferences, DashboardWidgetDefaults

# Phase 6: Saved Filters
from .saved_filter import SavedFilter, FilterHistory

# Phase 10: Workflow Foundation
from .workflow import WorkflowTransitionLog

# Dual-View Architecture Phase 2: Calculation Assumption Registry
from .calculation_assumption import (
    AssumptionChange,
    AssumptionStatus,
    CalculationAssumption,
    MetricAssumptionDependency,
)

# Dual-View Architecture Phase 3: Metric Calculation Results
from .metric_calculation_result import MetricCalculationResult

# Phase B.1: Capacity Planning (13 tables)
from .capacity import (
    CapacityCalendar,
    CapacityProductionLine,
    CapacityOrder,
    OrderPriority,
    OrderStatus,
    CapacityProductionStandard,
    CapacityBOMHeader,
    CapacityBOMDetail,
    CapacityStockSnapshot,
    CapacityComponentCheck,
    ComponentStatus,
    CapacityAnalysis,
    CapacitySchedule,
    CapacityScheduleDetail,
    ScheduleStatus,
    CapacityScenario,
    CapacityKPICommitment,
)

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
    "ShiftCoverage",
    # Phase 4
    "QualityEntry",
    "DefectDetail",
    "DefectType",
    # Phase 7.2
    "ClientConfig",
    "OTDMode",
    # Phase 3 Events
    "EventStore",
    # Import Log
    "ImportLog",
    # KPI Thresholds
    "KPIThreshold",
    # Phase 2.1 Junction tables
    "UserClientAssignment",
    "EmployeeClientAssignment",
    "AssignmentType",
    # Phase 9
    "DefectTypeCatalog",
    # Task 0.5
    "HoldStatusCatalog",
    "HoldReasonCatalog",
    # Sprint 1
    "BreakTime",
    # Sprint 2
    "ProductionLine",
    "Equipment",
    "EmployeeLineAssignment",
    # Phase 6
    "UserPreferences",
    "DashboardWidgetDefaults",
    "SavedFilter",
    "FilterHistory",
    # Phase 10
    "WorkflowTransitionLog",
    # Dual-View Phase 2
    "AssumptionChange",
    "AssumptionStatus",
    "CalculationAssumption",
    "MetricAssumptionDependency",
    # Dual-View Phase 3
    "MetricCalculationResult",
    # Phase B.1 Capacity Planning
    "CapacityCalendar",
    "CapacityProductionLine",
    "CapacityOrder",
    "OrderPriority",
    "OrderStatus",
    "CapacityProductionStandard",
    "CapacityBOMHeader",
    "CapacityBOMDetail",
    "CapacityStockSnapshot",
    "CapacityComponentCheck",
    "ComponentStatus",
    "CapacityAnalysis",
    "CapacitySchedule",
    "CapacityScheduleDetail",
    "ScheduleStatus",
    "CapacityScenario",
    "CapacityKPICommitment",
]
