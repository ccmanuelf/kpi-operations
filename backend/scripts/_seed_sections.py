"""
Section-builder helpers for the demo-client seeder. Each `seed_*` function is
an idempotent, INSERT-only builder for one slice of a client's dataset
(catalogs, config layer, master data, capacity planning graph, work orders,
holds, daily Operations data, simulation). Split out of seed_sample_client.py
so that module stays focused on CLI/orchestration.

No behavior change from the pre-split version — this is a pure move.
"""

import hashlib
import random
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from backend.orm.client import ClientType

if TYPE_CHECKING:
    from backend.orm import WorkOrderStatus


@dataclass(frozen=True)
class ClientSpec:
    client_id: str
    client_name: str
    client_type: ClientType
    num_employees: int
    num_work_orders: int


def rng_for(*key_parts: object) -> random.Random:
    """Deterministic RNG keyed on a stable sha256 of the parts (NOT builtin
    hash(), which is per-process salted for strings)."""
    key = "|".join(str(p) for p in key_parts).encode("utf-8")
    seed_int = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed_int)


_HOLD_STATUSES = [
    ("PENDING_HOLD_APPROVAL", "Pending Hold Approval", 1),
    ("ON_HOLD", "On Hold", 2),
    ("PENDING_RESUME_APPROVAL", "Pending Resume Approval", 3),
    ("RESUMED", "Resumed", 4),
    ("RELEASED", "Released", 5),
    ("CANCELLED", "Cancelled", 6),
    ("SCRAPPED", "Scrapped", 7),
]
_HOLD_REASONS = [
    ("QUALITY_ISSUE", "Quality Issue", 1),
    ("MATERIAL_SHORTAGE", "Material Shortage", 2),
    ("MATERIAL_INSPECTION", "Material Inspection", 3),
    ("ENGINEERING_REVIEW", "Engineering Review", 4),
    ("CUSTOMER_REQUEST", "Customer Request", 5),
    ("CAPACITY_CONSTRAINT", "Capacity Constraint", 6),
]
_DEFECT_TYPES = [
    ("STITCH", "Stitching", "SEWING", "MAJOR"),
    ("FABRIC", "Fabric Defect", "MATERIAL", "MAJOR"),
    ("MEASURE", "Measurement", "DIMENSIONAL", "MINOR"),
    ("COLOR", "Color Shade", "VISUAL", "MINOR"),
    ("STAIN", "Stain", "VISUAL", "MINOR"),
]
_KPI_THRESHOLDS = [
    ("efficiency", 85.0, 75.0, 60.0, "%", "Y"),
    ("performance", 95.0, 85.0, 70.0, "%", "Y"),
    ("quality_rate", 99.0, 97.0, 95.0, "%", "Y"),
    ("oee", 85.0, 75.0, 60.0, "%", "Y"),
    ("availability", 90.0, 80.0, 70.0, "%", "Y"),
    ("otd", 95.0, 90.0, 80.0, "%", "Y"),
]
_ALERT_CONFIGS = [
    ("efficiency", 75.0, 60.0),
    ("otd", 90.0, 80.0),
    ("quality", 97.0, 95.0),
]


def seed_catalogs(session: Session, client_id: str) -> None:
    """Idempotent per-client hold-status/hold-reason/defect-type catalogs."""
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog

    if session.query(HoldStatusCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, order in _HOLD_STATUSES:
            session.add(
                HoldStatusCatalog(
                    client_id=client_id,
                    status_code=code,
                    display_name=name,
                    is_default=True,
                    is_active=True,
                    sort_order=order,
                )
            )
    if session.query(HoldReasonCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, order in _HOLD_REASONS:
            session.add(
                HoldReasonCatalog(
                    client_id=client_id,
                    reason_code=code,
                    display_name=name,
                    is_default=True,
                    is_active=True,
                    sort_order=order,
                )
            )
    from backend.orm.defect_type_catalog import DefectTypeCatalog

    if session.query(DefectTypeCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, category, severity in _DEFECT_TYPES:
            session.add(
                DefectTypeCatalog(
                    defect_type_id=f"DEFECT-{client_id}-{code}",
                    client_id=client_id,
                    defect_code=code,
                    defect_name=name,
                    category=category,
                    severity_default=severity,
                )
            )
    session.flush()


def seed_config_layer(session: Session, client_id: str) -> None:
    """Idempotent per-client ClientConfig, KPIThreshold set, and AlertConfig set."""
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig

    if session.query(ClientConfig).filter_by(client_id=client_id).first() is None:
        session.add(ClientConfig(client_id=client_id))  # all targets have credible defaults
    if session.query(KPIThreshold).filter_by(client_id=client_id).first() is None:
        for kpi_key, target, warning, critical, unit, higher in _KPI_THRESHOLDS:
            session.add(
                KPIThreshold(
                    threshold_id=f"KPI-TH-{client_id}-{kpi_key.upper()}",
                    client_id=client_id,
                    kpi_key=kpi_key,
                    target_value=target,
                    warning_threshold=warning,
                    critical_threshold=critical,
                    unit=unit,
                    higher_is_better=higher,
                )
            )
    if session.query(AlertConfig).filter_by(client_id=client_id).first() is None:
        for alert_type, warning, critical in _ALERT_CONFIGS:
            session.add(
                AlertConfig(
                    config_id=f"ALERT-CFG-{client_id}-{alert_type.upper()}",
                    client_id=client_id,
                    alert_type=alert_type,
                    enabled=True,
                    warning_threshold=warning,
                    critical_threshold=critical,
                )
            )
    session.flush()


def seed_shifts(session: Session, client_id: str) -> list:
    """Idempotent per-client Day/Night shifts."""
    from backend.orm import Shift
    from backend.db.factories import TestDataFactory

    existing = session.query(Shift).filter_by(client_id=client_id).all()
    if existing:
        return existing
    day = TestDataFactory.create_shift(
        session, client_id=client_id, shift_name="Day", start_time="06:00:00", end_time="14:00:00"
    )
    night = TestDataFactory.create_shift(
        session, client_id=client_id, shift_name="Night", start_time="14:00:00", end_time="22:00:00"
    )
    return [day, night]


def seed_products(session: Session, client_id: str) -> list:
    """Idempotent per-client product catalog (3 garment products)."""
    from backend.orm import Product
    from decimal import Decimal
    from backend.db.factories import TestDataFactory

    existing = session.query(Product).filter_by(client_id=client_id).all()
    if existing:
        return existing
    specs = [
        (f"{client_id}-P1", "Polo Shirt", Decimal("0.12")),
        (f"{client_id}-P2", "T-Shirt", Decimal("0.08")),
        (f"{client_id}-P3", "Jacket", Decimal("0.30")),
    ]
    return [
        TestDataFactory.create_product(
            session, client_id=client_id, product_code=code, product_name=name, ideal_cycle_time=ct
        )
        for code, name, ct in specs
    ]


def seed_lines(session: Session, client_id: str) -> tuple[list, list]:
    """Idempotent per-client operational lines bridged to capacity lines."""
    from backend.orm.production_line import ProductionLine
    from backend.orm.capacity import CapacityProductionLine

    existing = session.query(ProductionLine).filter_by(client_id=client_id).all()
    if existing:
        cap = session.query(CapacityProductionLine).filter_by(client_id=client_id).all()
        return existing, cap
    lines, cap_lines = [], []
    for i in (1, 2):
        cap = CapacityProductionLine(
            client_id=client_id, line_code=f"{client_id}-CL{i}", line_name=f"Capacity Line {i}", is_active=True
        )
        session.add(cap)
        session.flush()  # get cap.id
        line = ProductionLine(
            client_id=client_id,
            line_code=f"{client_id}-L{i}",
            line_name=f"Line {i}",
            line_type="DEDICATED",
            is_active=True,
            capacity_line_id=cap.id,
        )
        session.add(line)
        lines.append(line)
        cap_lines.append(cap)
    session.flush()
    return lines, cap_lines


def seed_employees(session: Session, spec: ClientSpec) -> list:
    """Idempotent per-client employees, single-client-assigned, with client +
    line assignments."""
    from backend.orm.employee import Employee
    from backend.orm.employee_client_assignment import assign_employee_to_client
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from datetime import date
    from decimal import Decimal
    from backend.db.factories import TestDataFactory

    cid = spec.client_id
    existing = session.query(Employee).filter_by(client_id_assigned=cid).all()
    if existing:
        return existing
    lines, _ = seed_lines(session, cid)
    employees = []
    for n in range(1, spec.num_employees + 1):
        emp = TestDataFactory.create_employee(
            session,
            client_id=cid,
            employee_code=f"{cid}-EMP-{n:03d}",
            employee_name=f"{spec.client_name} Operator {n}",
        )
        assign_employee_to_client(session, employee_id=emp.employee_id, client_id=cid, assigned_by="SEED_SCRIPT")
        line = lines[(n - 1) % len(lines)]
        session.add(
            EmployeeLineAssignment(
                employee_id=emp.employee_id,
                line_id=line.line_id,
                client_id=cid,
                allocation_percentage=Decimal("100.00"),
                is_primary=True,
                effective_date=date(2026, 1, 1),
            )
        )
        employees.append(emp)
    session.flush()
    return employees


def seed_capacity_graph(session: Session, client_id: str, days: int, anchor: date) -> None:
    """Idempotent per-client capacity planning-scheduling graph: calendar,
    orders (spanning statuses/priorities), production standards, BOM
    header+detail, stock snapshots, component checks, a schedule + details,
    and KPI commitments. Uses the capacity lines created by seed_lines."""
    from datetime import timedelta
    from decimal import Decimal
    from backend.orm.capacity import (
        CapacityCalendar,
        CapacityOrder,
        OrderPriority,
        OrderStatus,
        CapacityProductionStandard,
        CapacityBOMHeader,
        CapacityBOMDetail,
        CapacityStockSnapshot,
        CapacityComponentCheck,
        ComponentStatus,
        CapacitySchedule,
        CapacityScheduleDetail,
        ScheduleStatus,
        CapacityKPICommitment,
        CapacityScenario,
        CapacityAnalysis,
    )

    if session.query(CapacityCalendar).filter_by(client_id=client_id).first() is not None:
        return

    rng = rng_for(client_id, "capacity")
    # Planning horizon spans FORWARD from the anchor (anchor + i days), i.e. it
    # begins where the Operations history (seed_work_orders/holds/daily_data,
    # all anchored on the same `anchor`) ends.
    today = anchor
    _, cap_lines = seed_lines(session, client_id)
    styles = [f"{client_id}-P1", f"{client_id}-P2", f"{client_id}-P3"]

    # --- Calendar: one row per day, working on weekdays ---
    for i in range(days):
        cal_date = today + timedelta(days=i)
        is_working = cal_date.weekday() < 5
        session.add(
            CapacityCalendar(
                client_id=client_id,
                calendar_date=cal_date,
                is_working_day=is_working,
                shifts_available=1 if is_working else 0,
                shift1_hours=8.0 if is_working else 0,
                shift2_hours=0,
                shift3_hours=0,
                holiday_name=None if is_working else "Weekend",
            )
        )

    # --- Orders: span every OrderStatus and a mix of OrderPriority ---
    order_defs = [
        (1, OrderStatus.DRAFT, OrderPriority.LOW),
        (2, OrderStatus.CONFIRMED, OrderPriority.NORMAL),
        (3, OrderStatus.SCHEDULED, OrderPriority.HIGH),
        (4, OrderStatus.IN_PROGRESS, OrderPriority.URGENT),
        (5, OrderStatus.COMPLETED, OrderPriority.NORMAL),
        (6, OrderStatus.CANCELLED, OrderPriority.LOW),
    ]
    orders = []
    for n, status, priority in order_defs:
        qty = rng.randint(500, 5000)
        order = CapacityOrder(
            client_id=client_id,
            order_number=f"{client_id}-ORD-{n:03d}",
            customer_name=f"{client_id} Retail Partner",
            style_model=styles[(n - 1) % len(styles)],
            style_description="Demo style",
            order_quantity=qty,
            completed_quantity=qty if status == OrderStatus.COMPLETED else 0,
            order_date=today,
            required_date=today + timedelta(days=14 + n * 3),
            priority=priority,
            status=status,
            notes="Seeded demo capacity order",
        )
        session.add(order)
        orders.append(order)
    session.flush()  # populate order.id for component checks / schedule details

    # --- Production Standards: SAM minutes per style/operation ---
    operations = [("CUT", "Cutting Operation", "CUTTING"), ("SEW", "Sewing Operation", "SEWING")]
    for style in styles:
        for op_code, op_name, dept in operations:
            sam = round(rng.uniform(0.5, 5.0), 2)
            session.add(
                CapacityProductionStandard(
                    client_id=client_id,
                    style_model=style,
                    operation_code=op_code,
                    operation_name=op_name,
                    department=dept,
                    sam_minutes=Decimal(str(sam)),
                )
            )

    # --- BOM: one parent item with >=2 components ---
    header = CapacityBOMHeader(
        client_id=client_id,
        parent_item_code=styles[0],
        parent_item_description="Demo BOM parent",
        style_model=styles[0],
        revision="1.0",
        is_active=True,
    )
    session.add(header)
    session.flush()  # populate header.id for details

    components = [
        ("FABRIC-MAIN", "Main Fabric", "M", "FABRIC"),
        ("THREAD-MAIN", "Thread", "M", "TRIM"),
        ("BUTTON-MAIN", "Button", "EA", "ACCESSORY"),
    ]
    for comp_code, comp_desc, uom, ctype in components:
        qty_per = round(rng.uniform(0.5, 3.0), 2)
        session.add(
            CapacityBOMDetail(
                header_id=header.id,
                client_id=client_id,
                component_item_code=f"{client_id}-{comp_code}",
                component_description=comp_desc,
                quantity_per=Decimal(str(qty_per)),
                unit_of_measure=uom,
                waste_percentage=Decimal("5.0"),
                component_type=ctype,
            )
        )

    # --- Stock Snapshots: one per component ---
    for comp_code, comp_desc, uom, _ctype in components:
        on_hand = Decimal(str(rng.randint(0, 5000)))
        session.add(
            CapacityStockSnapshot(
                client_id=client_id,
                snapshot_date=today,
                item_code=f"{client_id}-{comp_code}",
                item_description=comp_desc,
                on_hand_quantity=on_hand,
                allocated_quantity=Decimal("0"),
                on_order_quantity=Decimal("0"),
                available_quantity=on_hand,
                unit_of_measure=uom,
            )
        )

    # --- Component Checks: mix OK/SHORTAGE/PARTIAL against the orders ---
    status_cycle = [ComponentStatus.OK, ComponentStatus.SHORTAGE, ComponentStatus.PARTIAL]
    for i, order in enumerate(orders):
        item_code = f"{client_id}-{components[i % len(components)][0]}"
        required = Decimal(str(rng.randint(500, 5000)))
        target_status = status_cycle[i % len(status_cycle)]
        if target_status == ComponentStatus.OK:
            available = required + Decimal("100")
        elif target_status == ComponentStatus.SHORTAGE:
            available = Decimal("0")
        else:
            available = required / 2
        shortage = max(Decimal("0"), required - available)
        session.add(
            CapacityComponentCheck(
                client_id=client_id,
                run_date=today,
                order_id=order.id,
                order_number=order.order_number,
                component_item_code=item_code,
                component_description="Demo component availability check",
                required_quantity=required,
                available_quantity=available,
                shortage_quantity=shortage,
                status=target_status,
            )
        )

    # --- Schedule: one period over the window ---
    period_end = today + timedelta(days=max(days - 1, 0))
    schedule = CapacitySchedule(
        client_id=client_id,
        schedule_name=f"{client_id} Demo Schedule",
        period_start=today,
        period_end=period_end,
        status=ScheduleStatus.COMMITTED,
        notes="Seeded demo schedule",
    )
    session.add(schedule)
    session.flush()  # populate schedule.id for details / KPI commitments

    # --- Schedule Details: tie orders -> lines -> dates (skip cancelled orders) ---
    seq = 1
    for i, order in enumerate(orders):
        if order.status == OrderStatus.CANCELLED:
            continue
        line = cap_lines[i % len(cap_lines)]
        sched_date = today + timedelta(days=i)
        while sched_date.weekday() >= 5:
            sched_date += timedelta(days=1)
        qty = min(order.order_quantity, rng.randint(100, 1000))
        session.add(
            CapacityScheduleDetail(
                schedule_id=schedule.id,
                client_id=client_id,
                order_id=order.id,
                order_number=order.order_number,
                style_model=order.style_model,
                line_id=line.id,
                line_code=line.line_code,
                scheduled_date=sched_date,
                scheduled_quantity=qty,
                completed_quantity=qty if order.status == OrderStatus.COMPLETED else 0,
                sequence=seq,
            )
        )
        seq += 1

    # --- KPI Commitments ---
    kpi_defs = [
        ("efficiency", "Efficiency vs Standard %", Decimal("85.0"), Decimal("82.0")),
        ("otd", "On-Time Delivery %", Decimal("95.0"), Decimal("91.0")),
        ("quality", "Quality Rate %", Decimal("98.0"), Decimal("97.0")),
    ]
    for kpi_key, kpi_name, committed_val, actual_val in kpi_defs:
        commitment = CapacityKPICommitment(
            client_id=client_id,
            schedule_id=schedule.id,
            kpi_key=kpi_key,
            kpi_name=kpi_name,
            period_start=today,
            period_end=period_end,
            committed_value=committed_val,
            actual_value=actual_val,
            notes="Seeded demo KPI commitment",
        )
        commitment.calculate_variance()
        session.add(commitment)

    # --- Scenario: one what-if scenario referencing the seeded schedule ---
    scenario = CapacityScenario(
        client_id=client_id,
        scenario_name=f"{client_id} Overtime Scenario",
        scenario_type="OVERTIME",
        base_schedule_id=schedule.id,
        parameters_json={"overtime_hours_per_day": 2, "applies_to_lines": [line.line_code for line in cap_lines]},
        results_json={"capacity_increase_percent": 12.5, "cost_impact": 4200.0},
        is_active=True,
        notes="Seeded demo what-if scenario",
    )
    session.add(scenario)

    # --- Analysis: one 12-step capacity analysis per capacity line ---
    working_days = sum(1 for i in range(days) if (today + timedelta(days=i)).weekday() < 5)
    for line in cap_lines:
        arng = rng_for(client_id, "capacity", "analysis", line.line_code)
        analysis = CapacityAnalysis(
            client_id=client_id,
            analysis_date=today,
            line_id=line.id,
            line_code=line.line_code,
            department=line.department,
            working_days=working_days,
            shifts_per_day=1,
            hours_per_shift=Decimal("8.0"),
            operators_available=line.max_operators,
            efficiency_factor=line.efficiency_factor,
            absenteeism_factor=line.absenteeism_factor,
            demand_hours=Decimal("0"),
            demand_units=arng.randint(1000, 5000),
        )
        # First pass computes capacity_hours; then set demand to a credible
        # fraction of capacity so utilization reflects a busy-but-not-idle line.
        analysis.calculate_metrics()
        cap_h = float(analysis.capacity_hours or 0)
        target_util = arng.uniform(0.65, 0.95)
        analysis.demand_hours = Decimal(str(round(cap_h * target_util, 2)))
        analysis.calculate_metrics()
        session.add(analysis)

    session.flush()


def _production_target_fraction(status: "WorkOrderStatus") -> float:
    """Status-derived fraction of planned_quantity a WO should have produced
    (the plan-vs-actual true-up target). Terminal/shipped statuses are "done";
    in-flight statuses are partially complete; not-yet-started/cancelled WOs
    are zero. Shared by seed_work_orders (CapacityOrder alignment) and
    seed_daily_data (production distribution) so both land on the same number."""
    from backend.orm import WorkOrderStatus as S

    return {
        S.SHIPPED: 1.0,
        S.CLOSED: 1.0,
        S.COMPLETED: 1.0,
        S.IN_PROGRESS: 0.5,
        S.ON_HOLD: 0.3,
    }.get(status, 0.0)


def seed_work_orders(session: Session, spec: ClientSpec, entered_by: str, anchor: date) -> list:
    """Idempotent per-client work orders spanning every WorkOrderStatus, each
    with a credible WorkflowTransitionLog chain, status-coherent milestone
    dates, and (for mainline RELEASED..CLOSED statuses) a bridge to a seeded
    CapacityOrder — plus a few Jobs."""
    from datetime import datetime, timedelta, timezone
    from backend.orm import WorkOrder, WorkOrderStatus
    from backend.orm.capacity import CapacityOrder, OrderStatus
    from backend.db.factories import TestDataFactory

    cid = spec.client_id
    existing = session.query(WorkOrder).filter_by(client_id=cid).all()
    if existing:
        return existing

    states = [
        WorkOrderStatus.RECEIVED,
        WorkOrderStatus.RELEASED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.SHIPPED,
        WorkOrderStatus.CLOSED,
        WorkOrderStatus.CANCELLED,
        WorkOrderStatus.ON_HOLD,
    ]
    # Statuses in the linear RELEASED..CLOSED range get bridged to a
    # CapacityOrder (origin=CAPACITY_PLAN); RECEIVED (not yet released),
    # CANCELLED, and ON_HOLD (branches off the linear chain) stay AD_HOC.
    mainline_bridge_statuses = (
        WorkOrderStatus.RELEASED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.SHIPPED,
        WorkOrderStatus.CLOSED,
    )
    cap_orders = session.query(CapacityOrder).filter_by(client_id=cid).order_by(CapacityOrder.id).all()
    bridge_idx = 0
    rng = rng_for(cid, "work_orders")
    now = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)
    wos = []
    for i, status in enumerate(states, start=1):
        wo_id = f"WO-{cid}-{i:03d}"  # full client_id — work_order_id PK is GLOBALLY unique
        planned_ship = now - timedelta(days=rng.randint(5, 40))
        # delivered on time for terminal states so OTD computes both hit/miss
        delivered = (
            planned_ship + timedelta(days=rng.randint(-3, 6))
            if status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED)
            else None
        )
        wo = TestDataFactory.create_work_order(
            session,
            client_id=cid,
            work_order_id=wo_id,
            status=status,
            planned_quantity=rng.randint(500, 3000),
            planned_ship_date=planned_ship,
            priority=rng.choice(["HIGH", "MEDIUM", "LOW"]),
        )
        # create_work_order doesn't read actual_delivery_date via **kwargs; set directly.
        wo.actual_delivery_date = delivered

        # --- Milestones (status-coherent, anchor-relative, deterministic) ---
        wo.received_date = now - timedelta(days=rng.randint(30, 70))
        if status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED):
            wo.dispatch_date = wo.received_date + timedelta(days=rng.randint(2, 10))
            wo.shipped_date = delivered
        if status == WorkOrderStatus.CLOSED:
            wo.closure_date = (wo.shipped_date or now) + timedelta(days=rng.randint(1, 5))
        if status == WorkOrderStatus.ON_HOLD:
            wo.previous_status = WorkOrderStatus.IN_PROGRESS.value

        # --- Bridge to Capacity Planning (mainline WOs only) ---
        if status in mainline_bridge_statuses and cap_orders:
            cap = cap_orders[bridge_idx % len(cap_orders)]
            bridge_idx += 1
            wo.origin = "CAPACITY_PLAN"
            wo.capacity_order_id = cap.id
            wo.planned_start_date = now - timedelta(days=rng.randint(20, 60))
            # Re-align the bridged CapacityOrder to this WO's plan/status so the
            # two sides of the bridge stay coherent (single source of truth).
            target_qty = int(wo.planned_quantity * _production_target_fraction(status))
            cap.order_quantity = wo.planned_quantity
            cap.completed_quantity = target_qty
            cap.status = (
                OrderStatus.COMPLETED
                if status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED, WorkOrderStatus.COMPLETED)
                else OrderStatus.IN_PROGRESS if status == WorkOrderStatus.IN_PROGRESS else OrderStatus.CONFIRMED
            )

        # transition chain to the terminal status
        chain = _transition_chain(status)  # e.g. [None->RECEIVED, RECEIVED->RELEASED, ...]
        for frm, to in chain:
            TestDataFactory.create_workflow_transition(
                session,
                work_order_id=wo_id,
                from_status=(frm.value if frm else None),  # type: ignore[arg-type]
                to_status=to.value,
                transitioned_by=entered_by,
                client_id=cid,
            )
        if status in (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED):
            # explicit deterministic job_id (do NOT let the factory mint a _next_id PK)
            TestDataFactory.create_job(session, work_order_id=wo_id, client_id=cid, job_id=f"JOB-{cid}-{i:03d}")
        wos.append(wo)
    session.flush()
    return wos


def _transition_chain(status: "WorkOrderStatus") -> list:
    from backend.orm import WorkOrderStatus as S

    linear = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.COMPLETED, S.SHIPPED, S.CLOSED]
    if status in linear:
        upto = linear[: linear.index(status) + 1]
    elif status == S.CANCELLED:
        upto = [S.RECEIVED, S.RELEASED, S.CANCELLED]
    elif status == S.ON_HOLD:
        upto = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.ON_HOLD]
    else:
        upto = [status]
    prev: Optional["WorkOrderStatus"] = None
    chain: list = []
    for s in upto:
        chain.append((prev, s))
        prev = s
    return chain


def seed_holds(session: Session, client_id: str, work_orders: list, entered_by: str, anchor: date) -> None:
    # Construct HoldEntry directly: TestDataFactory.create_hold_entry mints
    # hold_entry_id via _next_id("HOLD") (process-local counter → cross-process
    # PK collision). Use a deterministic client-scoped PK instead.
    from datetime import datetime, timezone
    from backend.orm import HoldEntry, WorkOrderStatus

    if session.query(HoldEntry).filter_by(client_id=client_id).first() is not None:
        return
    if not work_orders:  # nothing to attach holds to
        return
    chain = [
        "PENDING_HOLD_APPROVAL",
        "ON_HOLD",
        "PENDING_RESUME_APPROVAL",
        "RESUMED",
        "RELEASED",
        "CANCELLED",
        "SCRAPPED",
    ]
    # The currently-open hold statuses must reference the WO that is actually
    # ON_HOLD (credibility: a hold row can't be "open" against a WO that has
    # already moved on). Resolved statuses may reference other WOs as before.
    open_statuses = {"PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL"}
    # Prefer the WO actually in ON_HOLD status for open holds; fall back to the
    # first WO if (defensively) none is ON_HOLD, so this never StopIteration-crashes.
    on_hold_wo = next((w for w in work_orders if w.status == WorkOrderStatus.ON_HOLD), work_orders[0])
    for i, hold_status in enumerate(chain, start=1):
        wo = on_hold_wo if hold_status in open_statuses else work_orders[i % len(work_orders)]
        session.add(
            HoldEntry(
                hold_entry_id=f"HOLD-{client_id}-{i:03d}",
                work_order_id=wo.work_order_id,
                client_id=client_id,
                hold_initiated_by=entered_by,
                hold_reason="QUALITY_ISSUE",
                hold_reason_category="QUALITY",
                hold_status=hold_status,
                hold_date=datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc),
            )
        )
    session.flush()


def seed_daily_data(session: Session, spec: ClientSpec, days: int, entered_by: str, anchor: date) -> None:
    """Idempotent credible daily Operations data on the first product/shift/
    line. Production is distributed PER WORK ORDER so cumulative units true-up
    to a status-derived target of planned_quantity (see
    _production_target_fraction): the LAST entry per WO is pinned so the sum
    exactly equals the target, and wo.actual_quantity is set to that total.
    Each production entry carries a QualityEntry + DefectDetail and
    (occasionally) a DowntimeEntry tied to the same WO. AttendanceEntry is
    per employee per working day, independent of the WO split. Construct
    every entity DIRECTLY with a deterministic client-scoped PK (see
    seed_holds docstring) — TestDataFactory.create_production_entry et al.
    mint _next_id counter PKs that collide across processes."""
    from datetime import datetime, timedelta
    from decimal import Decimal
    from backend.orm import (
        ProductionEntry,
        QualityEntry,
        DefectDetail,
        DowntimeEntry,
        AttendanceEntry,
        AbsenceType,
        WorkOrder,
    )

    cid = spec.client_id
    if session.query(ProductionEntry).filter_by(client_id=cid).first() is not None:
        return
    products = seed_products(session, cid)
    shifts = seed_shifts(session, cid)
    lines, _ = seed_lines(session, cid)
    employees = seed_employees(session, spec)
    work_orders = session.query(WorkOrder).filter_by(client_id=cid).order_by(WorkOrder.work_order_id).all()
    product, shift, line = products[0], shifts[0], lines[0]
    end = anchor
    ideal_ct = float(product.ideal_cycle_time or Decimal("0.12"))

    # Walk backward from the anchor collecting exactly `days` WORKING days
    # (weekends skipped without counting) so `days` maps to working-day
    # entries, not calendar days diluted by weekend skips.
    working_days: list = []
    offset = 0
    while len(working_days) < days:
        day = end - timedelta(days=offset)
        offset += 1
        if day.weekday() >= 5:
            continue
        working_days.append(day)
    working_days.reverse()

    # --- Production/Quality/Defect/Downtime: distributed per-WO to a
    # status-derived target, so cumulative units are plan-vs-actual coherent. ---
    seq = 0
    for wo in work_orders:
        target_total = int((wo.planned_quantity or 0) * _production_target_fraction(wo.status))
        if target_total <= 0:
            wo.actual_quantity = 0
            continue
        wrng = rng_for(cid, "daily", "wo", wo.work_order_id)
        num_entries = max(1, min(len(working_days), 4 if target_total >= 200 else 2))
        step = max(1, (len(working_days) - 1) // max(1, num_entries - 1)) if num_entries > 1 else 1
        base_per_entry = target_total // num_entries
        running = 0
        for k in range(num_entries):
            is_last = k == num_entries - 1
            day_idx = (len(working_days) - 1) if is_last else min(k * step, len(working_days) - 1)
            day = working_days[day_idx]
            day_dt = datetime.combine(day, datetime.min.time())

            if is_last:
                units = max(1, target_total - running)
            else:
                noise = wrng.uniform(0.9, 1.1)
                units = max(1, min(int(base_per_entry * noise), target_total - running - (num_entries - k - 1)))
            running += units
            seq += 1

            target_perf = wrng.uniform(0.82, 0.96)
            run_time = round(ideal_ct * units / target_perf, 2)
            downtime_h = round(run_time * wrng.uniform(0.05, 0.08), 2)
            setup_h = round(run_time * 0.02, 2)
            maint_h = round(run_time * 0.01, 2)
            actual_ct = round(run_time / units, 4)
            defects = max(1, int(units * wrng.uniform(0.003, 0.012)))
            scrap = defects // 3
            rework = defects - scrap
            efficiency = performance = min(100.0, max(0.01, round(target_perf * 100, 2)))
            quality_pct = min(100.0, max(0.01, round(100 - (defects + scrap) / units * 100, 2)))
            employees_present = max(0, len(employees) - (1 if wrng.random() < 0.15 else 0))

            session.add(
                ProductionEntry(
                    production_entry_id=f"PE-{cid}-{seq:04d}",
                    client_id=cid,
                    product_id=product.product_id,
                    shift_id=shift.shift_id,
                    line_id=line.line_id,
                    entered_by=entered_by,
                    production_date=day_dt,
                    shift_date=day_dt,
                    units_produced=units,
                    run_time_hours=Decimal(str(run_time)),
                    setup_time_hours=Decimal(str(setup_h)),
                    downtime_hours=Decimal(str(downtime_h)),
                    maintenance_hours=Decimal(str(maint_h)),
                    defect_count=defects,
                    scrap_count=scrap,
                    rework_count=rework,
                    employees_assigned=len(employees),
                    employees_present=employees_present,
                    ideal_cycle_time=Decimal(str(ideal_ct)),
                    actual_cycle_time=Decimal(str(actual_ct)),
                    efficiency_percentage=Decimal(str(efficiency)),
                    performance_percentage=Decimal(str(performance)),
                    quality_rate=Decimal(str(quality_pct)),
                    work_order_id=wo.work_order_id,
                )
            )

            qe_id = f"QE-{cid}-{seq:04d}"
            units_def = defects + scrap
            session.add(
                QualityEntry(
                    quality_entry_id=qe_id,
                    work_order_id=wo.work_order_id,
                    client_id=cid,
                    inspector_id=entered_by,
                    inspection_date=day_dt,
                    shift_date=day_dt,
                    units_inspected=units,
                    units_passed=units - units_def,
                    units_defective=units_def,
                    total_defects_count=units_def,
                    units_scrapped=scrap,
                    units_reworked=defects - scrap,
                )
            )
            session.add(
                DefectDetail(
                    defect_detail_id=f"DD-{cid}-{seq:04d}",
                    quality_entry_id=qe_id,
                    client_id_fk=cid,
                    defect_type="Stitching",
                    defect_count=defects,
                    severity="MINOR",
                )
            )
            if seq % 5 == 1:
                session.add(
                    DowntimeEntry(
                        downtime_entry_id=f"DT-{cid}-{seq:04d}",
                        client_id=cid,
                        work_order_id=wo.work_order_id,
                        reported_by=entered_by,
                        downtime_reason=wrng.choice(["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "CHANGEOVER"]),
                        shift_date=day_dt,
                        downtime_duration_minutes=int(downtime_h * 60),
                    )
                )
        # Invariant: the last entry is pinned to (target_total - running), so the
        # per-WO produced total must land EXACTLY on target. Assert it so a future
        # change to planned_quantity range / target fractions / num_entries that
        # broke the reservation budget (target_total < num_entries-1) fails loudly.
        assert running == target_total, f"true-up miss for {wo.work_order_id}: {running} != {target_total}"
        wo.actual_quantity = running

    # --- Attendance: one per employee per working day, independent of the
    # per-WO production split. ---
    for day_seq, day in enumerate(working_days, start=1):
        day_dt = datetime.combine(day, datetime.min.time())
        for j, emp in enumerate(employees, start=1):
            arng = rng_for(cid, "att", day.isoformat(), emp.employee_id)
            absent = arng.random() < 0.05
            session.add(
                AttendanceEntry(
                    attendance_entry_id=f"ATT-{cid}-{day_seq:04d}-{j:02d}",
                    employee_id=emp.employee_id,
                    client_id=cid,
                    shift_id=shift.shift_id,
                    shift_date=day_dt,
                    scheduled_hours=Decimal("8.0"),
                    actual_hours=Decimal("0") if absent else Decimal("8.0"),
                    absence_hours=Decimal("8.0") if absent else Decimal("0"),
                    absence_type=AbsenceType.UNSCHEDULED_ABSENCE if absent else None,
                    is_absent=1 if absent else 0,
                )
            )
    session.flush()


def seed_simulation(session: Session, client_id: str) -> None:
    """Idempotent per-client baseline SimulationScenario. config_json is a
    minimal, schema-valid SimulationConfig.model_dump() (one operation, one
    demand, one shift schedule) — the engine only needs a structurally valid
    payload for the demo Save/Load list, not a rich what-if scenario."""
    from backend.orm.simulation_scenario import SimulationScenario

    if session.query(SimulationScenario).filter_by(client_id=client_id).first() is not None:
        return
    from backend.simulation_v2.models import SimulationConfig, OperationInput, ScheduleConfig, DemandInput, DemandMode

    config = SimulationConfig(
        operations=[
            OperationInput(
                product=f"{client_id}-P1",
                step=1,
                operation="Sew seams",
                machine_tool="Overlock 4-thread",
                sam_min=2.5,
            )
        ],
        schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5),
        demands=[DemandInput(product=f"{client_id}-P1", bundle_size=10, daily_demand=500)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    ).model_dump(mode="json")
    session.add(
        SimulationScenario(
            name=f"{client_id} Baseline Scenario",
            client_id=client_id,
            config_json=config,
            description="Seeded baseline what-if scenario",
            is_active=True,
        )
    )
    session.flush()
