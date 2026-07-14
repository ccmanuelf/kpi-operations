"""
Prod-safe demo-client seeder. INSERT-only; refuses any client not on a fixed
allowlist; never creates/drops schema (Alembic is the single schema mechanism).

Populates DEMO clients with a full, credible dataset (master data, config/catalog
layer, capacity planning-scheduling graph, work-order/workflow/hold variety, daily
Operations data, a simulation scenario) so the app can be validated as a real user.

VM invocation:
  docker compose -f docker-compose.prod.yml exec backend \\
      python -m backend.scripts.seed_sample_client --days 90
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import random  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import TYPE_CHECKING, Optional  # noqa: E402

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.exc import ArgumentError, NoSuchModuleError, OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.orm.client import Client, ClientType  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy import Engine  # noqa: E402


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


ALLOWLIST = frozenset({"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"})
DEFAULT_CLIENTS = ("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID")


@dataclass(frozen=True)
class ClientSpec:
    client_id: str
    client_name: str
    client_type: ClientType
    num_employees: int
    num_work_orders: int


CLIENT_SPECS: dict[str, ClientSpec] = {
    "DEMO-PIECE": ClientSpec("DEMO-PIECE", "Demo Piece-Rate Garments", ClientType.PIECE_RATE, 8, 8),
    "DEMO-HOURLY": ClientSpec("DEMO-HOURLY", "Demo Hourly Assembly", ClientType.HOURLY_RATE, 8, 8),
    "DEMO-HYBRID": ClientSpec("DEMO-HYBRID", "Demo Hybrid Works", ClientType.HYBRID, 8, 8),
    "SAMPLE_REF": ClientSpec("SAMPLE_REF", "SAMPLE_REF", ClientType.PIECE_RATE, 8, 8),
}


def rng_for(*key_parts: object) -> random.Random:
    """Deterministic RNG keyed on a stable sha256 of the parts (NOT builtin
    hash(), which is per-process salted for strings)."""
    key = "|".join(str(p) for p in key_parts).encode("utf-8")
    seed_int = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed_int)


def ensure_migrated(engine: "Engine") -> None:
    """Refuse to touch a database Alembic hasn't built (never creates schema)."""
    insp = inspect(engine)
    if not (insp.has_table("alembic_version") and insp.has_table("CLIENT") and insp.has_table("USER")):
        raise SeedError(
            "database is not migrated (alembic_version/CLIENT/USER missing). "
            "Start the backend once (its entrypoint runs `alembic upgrade head`), then retry."
        )


def resolve_entered_by(session: Session, client_id: str) -> str:
    """Resolve a real USER.user_id for entered_by/inspector_id: prefer a
    client-scoped operator, else any admin. No users are created."""
    from backend.orm.user import User

    scoped = (
        session.query(User)
        .filter(User.client_id_assigned.isnot(None), User.client_id_assigned.contains(client_id))
        .first()
    )
    if scoped is not None:
        return scoped.user_id
    admin = session.query(User).filter(User.role == "admin").first()
    if admin is not None:
        return admin.user_id
    raise SeedError(f"no usable entered_by user for {client_id} (need a client operator or an admin).")


def seed_client_row(session: Session, spec: ClientSpec) -> None:
    """Idempotent CLIENT insert."""
    if session.get(Client, spec.client_id) is not None:
        return
    session.add(
        Client(
            client_id=spec.client_id,
            client_name=spec.client_name,
            client_type=spec.client_type,
            is_active=1,
        )
    )
    session.flush()


# Children-first ordered (ORM class, client-column) list for scoped reset.
# Completed here so reset is correct as later tasks bring tables online
# (deleting zero rows for a not-yet-seeded table is harmless). NEVER includes CLIENT.
def _reset_table_order() -> list[tuple[type, str]]:
    from backend.orm import (
        AttendanceEntry,
        DefectDetail,
        DowntimeEntry,
        HoldEntry,
        Job,
        ProductionEntry,
        QualityEntry,
        Shift,
        Product,
        WorkOrder,
        WorkflowTransitionLog,
    )
    from backend.orm.employee import Employee
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from backend.orm.employee_client_assignment import EmployeeClientAssignment
    from backend.orm.production_line import ProductionLine
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    from backend.orm.simulation_scenario import SimulationScenario
    from backend.orm.capacity import (
        CapacityKPICommitment,
        CapacityScheduleDetail,
        CapacitySchedule,
        CapacityComponentCheck,
        CapacityAnalysis,
        CapacityStockSnapshot,
        CapacityBOMDetail,
        CapacityBOMHeader,
        CapacityProductionStandard,
        CapacityOrder,
        CapacityScenario,
        CapacityCalendar,
        CapacityProductionLine,
    )

    return [
        (DefectDetail, "client_id_fk"),
        (QualityEntry, "client_id"),
        (ProductionEntry, "client_id"),
        (DowntimeEntry, "client_id"),
        (AttendanceEntry, "client_id"),
        (WorkflowTransitionLog, "client_id"),
        (HoldEntry, "client_id"),
        (Job, "client_id_fk"),
        (WorkOrder, "client_id"),
        (CapacityKPICommitment, "client_id"),  # child of CapacitySchedule
        (CapacityScheduleDetail, "client_id"),  # child of CapacitySchedule, CapacityOrder, CapacityProductionLine
        (CapacityScenario, "client_id"),  # child of CapacitySchedule
        (CapacitySchedule, "client_id"),
        (CapacityComponentCheck, "client_id"),  # child of CapacityOrder
        (CapacityAnalysis, "client_id"),  # child of CapacityProductionLine
        (CapacityStockSnapshot, "client_id"),
        (CapacityBOMDetail, "client_id"),  # child of CapacityBOMHeader
        (CapacityBOMHeader, "client_id"),
        (CapacityProductionStandard, "client_id"),
        (CapacityOrder, "client_id"),
        (CapacityCalendar, "client_id"),
        (EmployeeLineAssignment, "client_id"),  # child of ProductionLine, Employee
        (EmployeeClientAssignment, "client_id"),  # child of Employee
        (Employee, "client_id_assigned"),
        (Shift, "client_id"),  # child of ProductionLine (line_id, nullable)
        (Product, "client_id"),
        (ProductionLine, "client_id"),  # child of CapacityProductionLine
        (CapacityProductionLine, "client_id"),
        (SimulationScenario, "client_id"),
        (AlertConfig, "client_id"),
        (KPIThreshold, "client_id"),
        (ClientConfig, "client_id"),
        (HoldStatusCatalog, "client_id"),
        (HoldReasonCatalog, "client_id"),
        (DefectTypeCatalog, "client_id"),
    ]


RESET_TABLE_ORDER = _reset_table_order()


def reset_client_data(session: Session, client_id: str) -> None:
    """Delete ONLY this client's rows, children-first. Leaves CLIENT + other clients intact."""
    for cls, col in RESET_TABLE_ORDER:
        session.query(cls).filter(getattr(cls, col) == client_id).delete(synchronize_session=False)
    session.flush()


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


def seed_capacity_graph(session: Session, client_id: str, days: int) -> None:
    """Idempotent per-client capacity planning-scheduling graph: calendar,
    orders (spanning statuses/priorities), production standards, BOM
    header+detail, stock snapshots, component checks, a schedule + details,
    and KPI commitments. Uses the capacity lines created by seed_lines."""
    from datetime import date, timedelta
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
    )

    if session.query(CapacityCalendar).filter_by(client_id=client_id).first() is not None:
        return

    rng = rng_for(client_id, "capacity")
    today = date.today()
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

    session.flush()


def seed_client(session: Session, spec: ClientSpec, days: int) -> None:
    """Orchestrator — seed one client in FK order. Later tasks append their
    section calls here (catalogs/config → master data → capacity → work orders
    → holds → daily data → simulation)."""
    seed_client_row(session, spec)
    seed_catalogs(session, spec.client_id)
    seed_config_layer(session, spec.client_id)
    seed_shifts(session, spec.client_id)
    seed_products(session, spec.client_id)
    seed_lines(session, spec.client_id)
    seed_employees(session, spec)
    seed_capacity_graph(session, spec.client_id, days)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seed_sample_client",
        description="Seed DEMO clients with a full credible dataset (INSERT-only, allowlist-guarded).",
    )
    parser.add_argument("--client", default=None, help=f"one of {sorted(ALLOWLIST)}; default = the 3 DEMO-* clients")
    parser.add_argument("--days", type=int, default=90, help="days of daily Operations data (default 90)")
    parser.add_argument("--reset", action="store_true", help="delete this client's existing rows before seeding")
    args = parser.parse_args(argv)

    if args.client is not None and args.client not in ALLOWLIST:
        print(f"ERROR: {args.client!r} is not on the demo allowlist {sorted(ALLOWLIST)}; refusing.", file=sys.stderr)
        return 1
    targets = [args.client] if args.client else list(DEFAULT_CLIENTS)

    database_url = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")
    try:
        engine = create_engine(database_url)
    except (ArgumentError, NoSuchModuleError):
        print(
            "ERROR: invalid DATABASE_URL (unparseable URL or unknown dialect); check the environment/.env.",
            file=sys.stderr,
        )
        return 1

    try:
        ensure_migrated(engine)
        with Session(engine) as session:
            for client_id in targets:
                spec = CLIENT_SPECS[client_id]
                if args.reset:
                    reset_client_data(session, client_id)
                seed_client(session, spec, args.days)
                session.commit()
                print(f"Seeded {client_id} ({args.days} days).")
    except SeedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(f"ERROR: database unreachable: {exc.orig}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
