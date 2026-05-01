"""
Test that all ORM models are properly registered with SQLAlchemy Base.metadata.

This test module prevents the CRITICAL schema-ORM mismatch that caused
503 errors on fresh installs (2026-02-23). If a new ORM model is added
but not imported in backend/orm/__init__.py, these tests will fail.
"""

import importlib
import pkgutil

import pytest

import backend.orm  # noqa: F401 — triggers all model registrations

# Alert ORM models live in backend/schemas/ (inverted naming convention)
from backend.schemas.alert import Alert, AlertConfig, AlertHistory  # noqa: F401

from backend.database import Base


class TestAllORMTablesRegistered:
    """Verify the ORM model registry is complete."""

    def test_minimum_table_count(self):
        """Base.metadata must contain at least 45 tables.

        The project has 51 tables as of the deployment-readiness audit.
        The threshold of 45 allows some margin for intentional removals
        while catching major regressions (e.g. missing import blocks).
        """
        actual_tables = set(Base.metadata.tables.keys())
        MIN_EXPECTED_TABLES = 45

        assert len(actual_tables) >= MIN_EXPECTED_TABLES, (
            f"Expected at least {MIN_EXPECTED_TABLES} tables registered in "
            f"Base.metadata, got {len(actual_tables)}. "
            f"Tables found: {sorted(actual_tables)}"
        )

    def test_core_tables_present(self):
        """Every core ORM table must be discoverable via Base.metadata."""
        actual_tables = set(Base.metadata.tables.keys())

        # These are the tables that MUST exist for the application to function.
        # Grouped by feature area for readability.
        required_tables = {
            # Core entities
            "CLIENT",
            "USER",
            "EMPLOYEE",
            "FLOATING_POOL",
            # Work orders
            "WORK_ORDER",
            "JOB",
            "PART_OPPORTUNITIES",
            # Production
            "PRODUCT",
            "SHIFT",
            "PRODUCTION_ENTRY",
            # WIP & Downtime
            "HOLD_ENTRY",
            "DOWNTIME_ENTRY",
            # Attendance
            "ATTENDANCE_ENTRY",
            "COVERAGE_ENTRY",
            "shift_coverage",
            # Quality
            "QUALITY_ENTRY",
            "DEFECT_DETAIL",
            "DEFECT_TYPE_CATALOG",
            # Configuration
            "CLIENT_CONFIG",
            "KPI_THRESHOLD",
            # Events & Auditing
            "EVENT_STORE",
            "import_log",
            # Junction tables
            "USER_CLIENT_ASSIGNMENT",
            "EMPLOYEE_CLIENT_ASSIGNMENT",
            # Hold catalogs
            "HOLD_STATUS_CATALOG",
            "HOLD_REASON_CATALOG",
            # Sprint 1-2 additions
            "BREAK_TIME",
            "PRODUCTION_LINE",
            "EQUIPMENT",
            "EMPLOYEE_LINE_ASSIGNMENT",
            # User preferences & filters
            "USER_PREFERENCES",
            "DASHBOARD_WIDGET_DEFAULTS",
            "SAVED_FILTER",
            "FILTER_HISTORY",
            # Workflow
            "WORKFLOW_TRANSITION_LOG",
            # Dual-View Phase 2: assumption registry
            "CALCULATION_ASSUMPTION",
            "ASSUMPTION_CHANGE",
            "METRIC_ASSUMPTION_DEPENDENCY",
            # Dual-View Phase 3: calculation results
            "METRIC_CALCULATION_RESULT",
            # Alerts
            "ALERT",
            "ALERT_CONFIG",
            "ALERT_HISTORY",
            # Capacity planning
            "capacity_calendar",
            "capacity_production_lines",
            "capacity_orders",
            "capacity_production_standards",
            "capacity_bom_header",
            "capacity_bom_detail",
            "capacity_stock_snapshot",
            "capacity_component_check",
            "capacity_analysis",
            "capacity_schedule",
            "capacity_schedule_detail",
            "capacity_scenario",
            "capacity_kpi_commitment",
        }

        missing = required_tables - actual_tables
        assert not missing, (
            f"The following required tables are NOT registered in Base.metadata: "
            f"{sorted(missing)}. "
            f"Ensure each model is imported in backend/orm/__init__.py "
            f"(or backend/schemas/alert.py for Alert models)."
        )


class TestNoOrphanedORMFiles:
    """Verify every .py file in backend/orm/ is importable."""

    def test_all_orm_modules_importable(self):
        """Every non-private .py file in backend/orm/ must import without errors.

        If a new module is added to backend/orm/ but has a broken import,
        this test catches it before it reaches production.
        """
        orm_path = backend.orm.__path__
        orm_modules = {name for _, name, ispkg in pkgutil.iter_modules(orm_path) if not name.startswith("_")}

        # Sanity check — we know there are many modules
        assert len(orm_modules) >= 20, (
            f"Expected at least 20 ORM modules, found {len(orm_modules)}: " f"{sorted(orm_modules)}"
        )

        for module_name in sorted(orm_modules):
            try:
                importlib.import_module(f"backend.orm.{module_name}")
            except ImportError as e:
                pytest.fail(
                    f"backend.orm.{module_name} failed to import: {e}. "
                    f"Fix the import or add it to backend/orm/__init__.py."
                )

    def test_capacity_subpackage_importable(self):
        """The capacity sub-package and all its modules must be importable."""
        import backend.orm.capacity

        cap_path = backend.orm.capacity.__path__
        cap_modules = {name for _, name, ispkg in pkgutil.iter_modules(cap_path) if not name.startswith("_")}

        assert len(cap_modules) >= 10, (
            f"Expected at least 10 capacity modules, found {len(cap_modules)}: " f"{sorted(cap_modules)}"
        )

        for module_name in sorted(cap_modules):
            try:
                importlib.import_module(f"backend.orm.capacity.{module_name}")
            except ImportError as e:
                pytest.fail(f"backend.orm.capacity.{module_name} failed to import: {e}")
