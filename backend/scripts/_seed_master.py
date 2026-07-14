"""
Master-data builders for the demo-client seeder: shifts, products,
operational/capacity lines, employees, break times, equipment, and alerts.

No behavior change from the pre-split version — this is a pure move.
"""

from sqlalchemy.orm import Session

from backend.scripts._seed_common import ClientSpec

_BREAK_DEFS = [
    ("Morning Break", 120, 15),
    ("Lunch Break", 240, 30),
]

_EQUIPMENT_DEFS = [
    ("Industrial Sewing Machine", "Sewing Machine"),
    ("Overlock Machine", "Overlocker"),
]

_ALERT_DEFS = [
    ("efficiency", "warning", "Efficiency Below Target", "Efficiency has dropped below the warning threshold."),
    ("otd", "warning", "OTD at Risk", "On-time delivery is trending below target for open work orders."),
    ("quality", "critical", "Quality PPM Elevated", "Defect rate has crossed the critical threshold."),
]


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
    line assignments. The last (up to 2) employees are floating-pool:
    is_floating_pool=1, a FLOATING (rather than DEDICATED)
    EmployeeClientAssignment, and a FloatingPool availability row."""
    from backend.orm.employee import Employee
    from backend.orm.employee_client_assignment import assign_employee_to_client, AssignmentType
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from datetime import date
    from decimal import Decimal
    from backend.db.factories import TestDataFactory

    cid = spec.client_id
    existing = session.query(Employee).filter_by(client_id_assigned=cid).all()
    if existing:
        return existing
    lines, _ = seed_lines(session, cid)
    num_floating = min(2, spec.num_employees)
    employees = []
    for n in range(1, spec.num_employees + 1):
        is_floating = n > spec.num_employees - num_floating
        emp = TestDataFactory.create_employee(
            session,
            client_id=cid,
            employee_code=f"{cid}-EMP-{n:03d}",
            employee_name=f"{spec.client_name} Operator {n}",
            is_floating_pool=is_floating,
        )
        assignment_type = AssignmentType.FLOATING_POOL.value if is_floating else AssignmentType.DEDICATED.value
        assign_employee_to_client(
            session,
            employee_id=emp.employee_id,
            client_id=cid,
            assigned_by="SEED_SCRIPT",
            assignment_type=assignment_type,
        )
        if is_floating:
            TestDataFactory.create_floating_pool_assignment(
                session,
                employee_id=emp.employee_id,
                client_id=cid,
                current_assignment=cid,
                notes=f"Seeded floating-pool employee for {cid}",
            )
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


def seed_break_times(session: Session, client_id: str) -> None:
    """Idempotent per-client BreakTime rows: ~2 breaks (Morning 15 min @ 120,
    Lunch 30 min @ 240) for each of the client's Shifts."""
    from backend.orm import Shift
    from backend.orm.break_time import BreakTime

    if session.query(BreakTime).filter_by(client_id=client_id).first() is not None:
        return
    shifts = session.query(Shift).filter_by(client_id=client_id).all()
    for shift in shifts:
        for break_name, start_offset, duration in _BREAK_DEFS:
            session.add(
                BreakTime(
                    shift_id=shift.shift_id,
                    client_id=client_id,
                    break_name=break_name,
                    start_offset_minutes=start_offset,
                    duration_minutes=duration,
                    applies_to="ALL",
                    is_active=True,
                )
            )
    session.flush()


def seed_equipment(session: Session, client_id: str) -> None:
    """Idempotent per-client Equipment: ~2 typed rows per operational
    ProductionLine, with deterministic codes embedding client_id."""
    from backend.orm.production_line import ProductionLine
    from backend.orm.equipment import Equipment

    if session.query(Equipment).filter_by(client_id=client_id).first() is not None:
        return
    lines = session.query(ProductionLine).filter_by(client_id=client_id, is_active=True).all()
    n = 0
    for line in lines:
        for equipment_name, equipment_type in _EQUIPMENT_DEFS:
            n += 1
            session.add(
                Equipment(
                    client_id=client_id,
                    line_id=line.line_id,
                    equipment_code=f"{client_id}-EQ-{n}",
                    equipment_name=equipment_name,
                    equipment_type=equipment_type,
                    status="ACTIVE",
                    is_active=True,
                )
            )
    session.flush()


def seed_alerts(session: Session, client_id: str) -> None:
    """Idempotent per-client Alert rows: ~3 active alerts, mixed category/severity."""
    from backend.orm.alert import Alert

    if session.query(Alert).filter_by(client_id=client_id).first() is not None:
        return
    for n, (category, severity, title, message) in enumerate(_ALERT_DEFS, start=1):
        session.add(
            Alert(
                alert_id=f"ALERT-{client_id}-{n}",
                client_id=client_id,
                category=category,
                severity=severity,
                status="active",
                title=title,
                message=message,
            )
        )
    session.flush()
