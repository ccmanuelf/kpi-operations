"""Two-tenant database fixture for cross-tenant authorization probing.

Built by INSERTing rows directly for two clients across every client-scoped
ORM model that a by-id route can reach. Deliberately independent of
``backend.seed`` — ``COVERAGE_ENTRY``, ``ALERT``, ``FLOATING_POOL``,
``SIMULATION_SCENARIO`` and ``CALCULATION_ASSUMPTION`` have zero rows in both
seed profiles, so a security fixture built on the seeder inherits its gaps and
is silently narrowed by every future seeder change.

Ids are deterministic and tenant-encoded so a probe can name what it asked for:
integer PKs are ``1`` for tenant A and ``2`` for tenant B; string PKs are
``<client_id>-<KIND>-1``.

Consumed by ``backend/tests/test_security/test_permission_matrix.py``
(``TestCrossTenantByIdRoutes``).
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

TENANT_A = "TEN-A"
TENANT_B = "TEN-B"

# Employee ids are global: EMPLOYEE has no client_id column. Ownership is the
# comma-separated EMPLOYEE.client_id_assigned (what the employee CRUD filters
# on, and what seed/writers_master.py writes); the EMPLOYEE_CLIENT_ASSIGNMENT
# junction row is populated too because it exists in the schema.
EMPLOYEE_A = 101
EMPLOYEE_B = 201
#: Employee with client_id_assigned NULL — the documented "floating pool"
#: shape (EmployeeCreate). Deliberately visible to both tenants; pinned by
#: test_permission_matrix.py::TestCrossTenantByIdRoutes
#: ::test_unassigned_employee_is_visible_to_every_tenant.
EMPLOYEE_SHARED = 301
#: A client whose id CONTAINS tenant A's, and an employee that belongs to it.
#: A substring `LIKE '%TEN-A%'` matches this row while the by-id route's
#: comma-exact check does not, so the listing and the by-id route disagree
#: about the same employee. Pinned by
#: test_permission_matrix.py::TestCrossTenantByIdRoutes
#: ::test_employee_listing_agrees_with_by_id_route_on_colliding_client_ids.
TENANT_A_LOOKALIKE = "TEN-A-WEST"
EMPLOYEE_LOOKALIKE = 401

_INT_PK = {TENANT_A: 1, TENANT_B: 2}

_D = date(2026, 8, 1)
_DT = datetime(2026, 8, 1, 6, 0, 0)

# The two tenants must differ in every measured quantity. A symmetric fixture
# makes aggregate routes (calendar hours, pivot totals, Bradford factor,
# inferred cycle time) return identical bodies for both tenants, so an
# unscoped route is indistinguishable from a scoped one. Asserted by
# test_permission_matrix.py::TestCrossTenantByIdRoutes::test_tenants_are_asymmetric.
_ASYM: dict[str, dict[str, Any]] = {
    TENANT_A: {
        "shift_end": time(14, 0),
        "cal_shift1_hours": 8,
        "cal_shifts_available": 1,
        "units_produced": 10,
        "run_time_hours": 8,
        "units_inspected": 10,
        "units_passed": 9,
        "units_defective": 1,
        "defect_count": 1,
        "downtime_minutes": 30,
        "is_absent": 0,
        "absence_hours": 0,
        "actual_hours": 8,
    },
    TENANT_B: {
        "shift_end": time(12, 0),
        "cal_shift1_hours": 5.25,
        "cal_shifts_available": 2,
        "units_produced": 7771,
        "run_time_hours": 6,
        "units_inspected": 8881,
        "units_passed": 7890,
        "units_defective": 991,
        "defect_count": 771,
        "downtime_minutes": 6661,
        "is_absent": 1,
        "absence_hours": 7,
        "actual_hours": 1,
    },
}


#: Values that appear ONLY in tenant B's rows and are odd enough that they
#: cannot show up by accident in an id, a timestamp or a count. A cross-tenant
#: 2xx body containing any of these is carrying tenant B's data even when it
#: contains no tenant id at all — which is how the calendar aggregates leaked.
#: Consumed by test_permission_matrix.py's universal guard.
_MARKER_KEYS = (
    "units_produced",
    "units_inspected",
    "units_passed",
    "units_defective",
    "defect_count",
    "downtime_minutes",
    "cal_shift1_hours",
)


def asym(client_id: str, key: str) -> Any:
    """Per-tenant value that makes an aggregate response discriminating."""
    return _ASYM[client_id][key]


def marker_values(client_id: str) -> tuple[str, ...]:
    """Stringified values unique to ``client_id``'s rows, for body scanning."""
    other = TENANT_B if client_id == TENANT_A else TENANT_A
    out = []
    for key in _MARKER_KEYS:
        mine, theirs = _ASYM[client_id][key], _ASYM[other][key]
        if mine == theirs:
            continue
        out.append(str(mine))
        if isinstance(mine, float):
            out.append(str(int(mine)) if mine.is_integer() else f"{mine}")
    return tuple(dict.fromkeys(out))


def str_pk(client_id: str, kind: str) -> str:
    """String primary key for ``kind`` owned by ``client_id``."""
    return f"{client_id}-{kind}-1"


def int_pk(client_id: str) -> int:
    """Integer primary key for any single-row-per-tenant table."""
    return _INT_PK[client_id]


def employee_of(client_id: str) -> int:
    return EMPLOYEE_A if client_id == TENANT_A else EMPLOYEE_B


def _tenant_rows(client_id: str) -> list[Any]:
    """Every client-scoped row for one tenant, in FK-safe insertion order."""
    from backend.orm.alert import Alert
    from backend.orm.attendance_entry import AttendanceEntry
    from backend.orm.break_time import BreakTime
    from backend.orm.calculation_assumption import CalculationAssumption
    from backend.orm.capacity import (
        CapacityBOMDetail,
        CapacityBOMHeader,
        CapacityCalendar,
        CapacityOrder,
        CapacityProductionLine,
        CapacityProductionStandard,
        CapacityScenario,
        CapacitySchedule,
        CapacityStockSnapshot,
    )
    from backend.orm.client_config import ClientConfig
    from backend.orm.coverage import ShiftCoverage
    from backend.orm.coverage_entry import CoverageEntry
    from backend.orm.defect_detail import DefectDetail
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    from backend.orm.downtime_entry import DowntimeEntry
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from backend.orm.equipment import Equipment
    from backend.orm.floating_pool import FloatingPool
    from backend.orm.hold_entry import HoldEntry
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.job import Job
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.metric_calculation_result import MetricCalculationResult
    from backend.orm.part_opportunities import PartOpportunities
    from backend.orm.product import Product
    from backend.orm.production_entry import ProductionEntry
    from backend.orm.production_line import ProductionLine
    from backend.orm.quality_entry import QualityEntry
    from backend.orm.shift import Shift
    from backend.orm.simulation_scenario import SimulationScenario
    from backend.orm.work_order import WorkOrder

    c = client_id
    n = int_pk(c)
    emp = employee_of(c)

    def a(key: str) -> Any:
        return asym(c, key)

    return [
        Shift(
            shift_id=n,
            client_id=c,
            shift_name=f"{c}-Day",
            start_time=time(6, 0),
            end_time=a("shift_end"),
        ),
        ProductionLine(line_id=n, client_id=c, line_code=f"{c}-L1", line_name=f"{c} Line 1"),
        Product(product_id=n, client_id=c, product_code=f"{c}-P1", product_name=f"{c} Product 1"),
        Equipment(equipment_id=n, client_id=c, equipment_code=f"{c}-EQ1", equipment_name=f"{c} Equipment 1"),
        BreakTime(
            break_id=n,
            shift_id=n,
            client_id=c,
            break_name=f"{c} Lunch",
            start_offset_minutes=240,
            duration_minutes=30,
        ),
        EmployeeLineAssignment(assignment_id=n, employee_id=emp, line_id=n, client_id=c, effective_date=_D),
        FloatingPool(pool_id=n, client_id=c, employee_id=emp),
        ShiftCoverage(
            coverage_id=n,
            client_id=c,
            shift_id=n,
            coverage_date=_D,
            required_employees=5,
            actual_employees=5,
            coverage_percentage=100,
            entered_by="seed",
        ),
        CoverageEntry(
            coverage_entry_id=str_pk(c, "CE"),
            client_id=c,
            floating_employee_id=emp,
            covered_employee_id=emp,
            shift_date=_DT,
        ),
        ClientConfig(config_id=n, client_id=c),
        CalculationAssumption(
            assumption_id=n,
            client_id=c,
            assumption_name=f"{c}_assumption",
            value_json="1.0",
            proposed_by="seed",
        ),
        MetricCalculationResult(
            result_id=n,
            client_id=c,
            metric_name="oee",
            period_start=_DT,
            period_end=_DT,
            standard_value_json="1.0",
            site_adjusted_value_json="1.0",
        ),
        KPIThreshold(threshold_id=str_pk(c, "TH"), client_id=c, kpi_key="oee", target_value=85.0),
        DefectTypeCatalog(defect_type_id=str_pk(c, "DT"), client_id=c, defect_code="COLOR", defect_name=f"{c} Color"),
        HoldReasonCatalog(catalog_id=n, client_id=c, reason_code="QUALITY", display_name=f"{c} Quality"),
        HoldStatusCatalog(catalog_id=n, client_id=c, status_code="OPEN", display_name=f"{c} Open"),
        PartOpportunities(
            part_number=str_pk(c, "PART"),
            client_id_fk=c,
            opportunities_per_unit=3,
            part_category=f"{c}-CAT",
        ),
        SimulationScenario(id=n, client_id=c, name=f"{c} Scenario", config_json={}),
        Alert(
            alert_id=str_pk(c, "AL"),
            client_id=c,
            category="quality",
            severity="critical",
            title=f"{c} alert",
            message=f"{c} alert message",
        ),
        WorkOrder(
            work_order_id=str_pk(c, "WO"),
            client_id=c,
            style_model=f"{c}-STYLE",
            planned_quantity=100,
        ),
        Job(
            job_id=str_pk(c, "JOB"),
            work_order_id=str_pk(c, "WO"),
            client_id_fk=c,
            operation_name=f"{c} Operation",
            sequence_number=1,
        ),
        ProductionEntry(
            production_entry_id=str_pk(c, "PE"),
            client_id=c,
            product_id=n,
            shift_id=n,
            production_date=_DT,
            shift_date=_DT,
            units_produced=a("units_produced"),
            run_time_hours=a("run_time_hours"),
            employees_assigned=5,
            entered_by="seed",
        ),
        QualityEntry(
            quality_entry_id=str_pk(c, "QE"),
            client_id=c,
            work_order_id=str_pk(c, "WO"),
            shift_date=_DT,
            units_inspected=a("units_inspected"),
            units_passed=a("units_passed"),
            units_defective=a("units_defective"),
            total_defects_count=a("defect_count"),
        ),
        DefectDetail(
            defect_detail_id=str_pk(c, "DD"),
            quality_entry_id=str_pk(c, "QE"),
            client_id_fk=c,
            defect_type="COLOR",
            defect_count=a("defect_count"),
        ),
        DowntimeEntry(
            downtime_entry_id=str_pk(c, "DE"),
            client_id=c,
            shift_date=_DT,
            downtime_reason="MAINTENANCE",
            downtime_duration_minutes=a("downtime_minutes"),
        ),
        AttendanceEntry(
            attendance_entry_id=str_pk(c, "AE"),
            client_id=c,
            employee_id=emp,
            shift_date=_DT,
            scheduled_hours=8,
            actual_hours=a("actual_hours"),
            absence_hours=a("absence_hours"),
            is_absent=a("is_absent"),
        ),
        HoldEntry(hold_entry_id=str_pk(c, "HE"), client_id=c, work_order_id=str_pk(c, "WO")),
        CapacityProductionLine(id=n, client_id=c, line_code=f"{c}-CL1", line_name=f"{c} Cap Line"),
        CapacityCalendar(
            id=n,
            client_id=c,
            calendar_date=_D,
            shifts_available=a("cal_shifts_available"),
            shift1_hours=a("cal_shift1_hours"),
        ),
        CapacityOrder(
            id=n,
            client_id=c,
            order_number=f"{c}-ORD-1",
            style_model=f"{c}-STYLE",
            order_quantity=100,
            required_date=_D,
        ),
        CapacityProductionStandard(id=n, client_id=c, style_model=f"{c}-STYLE", operation_code="OP1", sam_minutes=1),
        CapacityScenario(id=n, client_id=c, scenario_name=f"{c} Cap Scenario"),
        CapacitySchedule(id=n, client_id=c, schedule_name=f"{c} Schedule", period_start=_D, period_end=_D),
        CapacityBOMHeader(id=n, client_id=c, parent_item_code=f"{c}-ITEM"),
        CapacityBOMDetail(id=n, header_id=n, client_id=c, component_item_code=f"{c}-COMP"),
        CapacityStockSnapshot(id=n, client_id=c, snapshot_date=_D, item_code=f"{c}-ITEM"),
    ]


def build_two_tenant_db(db: Session) -> None:
    """Populate ``db`` with one row per client-scoped table for both tenants."""
    from backend.orm.client import Client
    from backend.orm.employee import Employee
    from backend.orm.employee_client_assignment import EmployeeClientAssignment
    from backend.orm.user_client_assignment import UserClientAssignment
    from backend.orm.saved_filter import SavedFilter
    from backend.orm.user import User

    for c in (TENANT_A, TENANT_B):
        db.add(Client(client_id=c, client_name=f"{c} Manufacturing"))
    db.flush()

    for c in (TENANT_A, TENANT_B):
        emp = employee_of(c)
        db.add(
            Employee(
                employee_id=emp,
                employee_code=f"{c}-E1",
                employee_name=f"{c} Employee",
                # Ownership column the employee CRUD actually filters on; the
                # junction row below exists too because get_user_client_filter
                # prefers it for USERS.
                client_id_assigned=c,
            )
        )
        db.flush()
        db.add(EmployeeClientAssignment(assignment_id=int_pk(c), employee_id=emp, client_id=c))
    db.add(Client(client_id=TENANT_A_LOOKALIKE, client_name="Lookalike Manufacturing"))
    db.flush()
    db.add(
        Employee(
            employee_id=EMPLOYEE_LOOKALIKE,
            employee_code="WEST-E1",
            employee_name="Lookalike Employee",
            client_id_assigned=TENANT_A_LOOKALIKE,
        )
    )
    db.add(
        Employee(
            employee_id=EMPLOYEE_SHARED,
            employee_code="SHARED-E1",
            employee_name="Shared Floating Employee",
            client_id_assigned=None,
            is_floating_pool=1,
        )
    )
    db.flush()

    for c in (TENANT_A, TENANT_B):
        for row in _tenant_rows(c):
            db.add(row)
        db.flush()

    # Personas that must NOT be denied. Over-denial is the failure mode a
    # tenant fix causes, and it is invisible unless something exercises the
    # roles that legitimately see more than one client:
    #   * admin/poweruser  -> get_user_client_filter returns None ("all")
    #   * multi-client leader -> a comma list
    #   * the whitespace variant, which only works because
    #     _get_clients_from_legacy_field strips each token
    for user_id, username, role, assigned in (
        ("USR-ADMIN", "admin_all", "admin", None),
        ("USR-POWER", "power_all", "poweruser", None),
        ("USR-LEADER-AB", "leader_ab", "leader", f"{TENANT_A},{TENANT_B}"),
        ("USR-LEADER-WS", "leader_ws", "leader", f"{TENANT_A}, {TENANT_B}"),
        # Assignment lives ONLY in USER_CLIENT_ASSIGNMENT (added below), which
        # get_user_client_filter can read only when it is handed a db session.
        # A call site that omits `db` denies this leader their own client.
        ("USR-JUNCTION", "junction_leader", "leader", None),
    ):
        db.add(
            User(
                user_id=user_id,
                username=username,
                email=f"{username}@test.com",
                password_hash="x",
                role=role,
                client_id_assigned=assigned,
                is_active=True,
            )
        )
    db.flush()
    db.add(UserClientAssignment(user_id="USR-JUNCTION", client_id=TENANT_A, is_active=True))
    db.flush()

    for c in (TENANT_A, TENANT_B):
        db.add(
            User(
                user_id=f"USR-{c}",
                username=f"sup_{c.lower()}",
                email=f"sup_{c.lower()}@test.com",
                password_hash="x",
                role="supervisor",
                client_id_assigned=c,
                is_active=True,
            )
        )
        db.flush()
        db.add(
            SavedFilter(
                filter_id=int_pk(c),
                user_id=f"USR-{c}",
                filter_name=f"{c} filter",
                filter_type="production",
                filter_config="{}",
                is_default=True,
            )
        )
    db.commit()
