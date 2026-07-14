"""
Capacity planning-scheduling graph builder for the demo-client seeder.

No behavior change from the pre-split version — this is a pure move.
"""

from datetime import date

from sqlalchemy.orm import Session

from backend.scripts._seed_common import rng_for
from backend.scripts._seed_master import seed_lines


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
