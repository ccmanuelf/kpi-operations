"""Baseline migration — stamps current schema state.

This migration is intentionally empty.  It exists so that Alembic has a
starting revision to track against.  On an existing database that was
created by ``Base.metadata.create_all()``, run:

    cd backend && python -m alembic stamp head

to mark it as up-to-date without executing any DDL.

On a brand-new database the tables are still created by
``Base.metadata.create_all()`` in the application lifespan; this
migration simply records that the baseline schema is in place.

Tables managed by Base.metadata.create_all():
  Core:
    - CLIENT, USER, SHIFT, EMPLOYEE, PRODUCT
    - FLOATING_POOL
  Work Orders:
    - WORK_ORDER, JOB, PART_OPPORTUNITIES
  Production:
    - PRODUCTION_ENTRY
  WIP & Downtime:
    - HOLD_ENTRY, DOWNTIME_ENTRY
  Attendance:
    - ATTENDANCE_ENTRY, COVERAGE_ENTRY
  Quality:
    - QUALITY_ENTRY, DEFECT_DETAIL, DEFECT_TYPE_CATALOG
  Catalogs:
    - HOLD_STATUS_CATALOG, HOLD_REASON_CATALOG
  Break Times:
    - BREAK_TIME
  Production Line Topology:
    - PRODUCTION_LINE, EQUIPMENT, EMPLOYEE_LINE_ASSIGNMENT
  User Preferences:
    - USER_PREFERENCES, DASHBOARD_WIDGET_DEFAULTS
  Saved Filters:
    - SAVED_FILTER, FILTER_HISTORY
  Workflow:
    - WORKFLOW_TRANSITION_LOG

Tables managed by capacity_planning_tables.py:
  - capacity_calendar
  - capacity_production_lines
  - capacity_orders
  - capacity_production_standards
  - capacity_bom_header
  - capacity_bom_detail
  - capacity_stock_snapshot
  - capacity_component_check
  - capacity_analysis
  - capacity_schedule
  - capacity_schedule_detail
  - capacity_scenario
  - capacity_kpi_commitment

Revision ID: 001_baseline
Revises: —
Create Date: 2026-02-22 (manual)
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op — baseline schema already exists via create_all()."""
    pass


def downgrade() -> None:
    """No-op — cannot reverse baseline; drop database manually if needed."""
    pass
