"""
Test Data Seeding Utilities
Provides functions to seed test databases with realistic, interconnected data.
Supports different test scenarios: minimal, comprehensive, multi-tenant.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from .factories import TestDataFactory
from backend.schemas import ClientType, WorkOrderStatus, HoldStatus, AbsenceType


def seed_minimal_data(db: Session) -> Dict[str, Any]:
    """
    Seed minimal data for quick unit tests.
    Creates one client, one user, one product, one shift.

    Args:
        db: Database session

    Returns:
        Dict with created entities for test reference
    """
    TestDataFactory.reset_counters()

    # Create client
    client = TestDataFactory.create_client(
        db,
        client_id="TEST-MIN",
        client_name="Minimal Test Client",
        client_type=ClientType.HOURLY_RATE
    )

    # Create user (assigned to client)
    user = TestDataFactory.create_user(
        db,
        username="min_user",
        role="supervisor",
        client_id=client.client_id,
        password="TestPass123!"
    )

    # Create product (scoped to client)
    product = TestDataFactory.create_product(
        db,
        client_id=client.client_id,
        product_code="PROD-MIN-001",
        product_name="Minimal Test Product",
        ideal_cycle_time=Decimal("0.15")
    )

    # Create shift (scoped to client)
    shift = TestDataFactory.create_shift(
        db,
        client_id=client.client_id,
        shift_name="Day Shift",
        start_time="06:00:00",
        end_time="14:00:00"
    )

    db.commit()

    return {
        "client": client,
        "user": user,
        "product": product,
        "shift": shift,
    }


def seed_comprehensive_data(
    db: Session,
    days_of_data: int = 30
) -> Dict[str, Any]:
    """
    Seed comprehensive data for integration tests.
    Creates full data hierarchy with production, quality, attendance, etc.

    Args:
        db: Database session
        days_of_data: Number of days of historical data to generate

    Returns:
        Dict with all created entities organized by type
    """
    TestDataFactory.reset_counters()

    # ========================================================================
    # Core Foundation
    # ========================================================================

    client = TestDataFactory.create_client(
        db,
        client_id="TEST-COMP",
        client_name="Comprehensive Test Client",
        client_type=ClientType.HOURLY_RATE
    )

    # Create users with different roles
    admin = TestDataFactory.create_user(
        db, username="comp_admin", role="admin", client_id=None
    )
    supervisor = TestDataFactory.create_user(
        db, username="comp_supervisor", role="supervisor", client_id=client.client_id
    )
    operator = TestDataFactory.create_user(
        db, username="comp_operator", role="operator", client_id=client.client_id
    )

    # Create employees (assigned to client)
    employees = []
    for i in range(10):
        emp = TestDataFactory.create_employee(
            db,
            client_id=client.client_id,
            employee_name=f"Employee {i+1}",
            employee_code=f"EMP-{i+1:03d}",
            is_floating_pool=(i >= 8)  # Last 2 are floating pool
        )
        employees.append(emp)

    # ========================================================================
    # Products & Shifts (scoped to client)
    # ========================================================================

    products = []
    product_data = [
        ("SHIRT", "T-Shirt Assembly", Decimal("0.15")),
        ("POLO", "Polo Shirt Production", Decimal("0.25")),
        ("JACKET", "Work Jacket Assembly", Decimal("0.50")),
    ]
    for code, name, cycle_time in product_data:
        prod = TestDataFactory.create_product(
            db,
            client_id=client.client_id,
            product_code=f"PROD-{code}-001",
            product_name=name,
            ideal_cycle_time=cycle_time
        )
        products.append(prod)

    shifts = []
    shift_data = [
        ("Morning", "06:00:00", "14:00:00"),
        ("Afternoon", "14:00:00", "22:00:00"),
        ("Night", "22:00:00", "06:00:00"),
    ]
    for name, start, end in shift_data:
        shift = TestDataFactory.create_shift(
            db,
            client_id=client.client_id,
            shift_name=f"{name} Shift",
            start_time=start,
            end_time=end
        )
        shifts.append(shift)

    db.flush()

    # ========================================================================
    # Work Orders & Jobs
    # ========================================================================

    work_orders = []
    jobs = []
    base_date = date.today() - timedelta(days=days_of_data)

    for i in range(5):
        wo = TestDataFactory.create_work_order(
            db,
            client_id=client.client_id,
            work_order_id=f"WO-TEST-{i+1:03d}",
            style_model=f"STYLE-{i+1:03d}",
            status=WorkOrderStatus.IN_PROGRESS if i < 3 else WorkOrderStatus.RECEIVED,
            planned_quantity=1000 * (i + 1),
            received_date=datetime.combine(base_date + timedelta(days=i * 5), datetime.min.time()),
            planned_ship_date=datetime.combine(base_date + timedelta(days=30 + i * 5), datetime.min.time()),
        )
        work_orders.append(wo)

        # Create jobs for each work order
        for j in range(2):
            job = TestDataFactory.create_job(
                db,
                work_order_id=wo.work_order_id,
                client_id=client.client_id,
                job_id=f"JOB-{i+1:03d}-{j+1}",
                part_number=f"PART-{i+1:03d}-{j+1}",
                quantity_required=wo.planned_quantity // 2
            )
            jobs.append(job)

            # Create part opportunities
            TestDataFactory.create_part_opportunities(
                db,
                part_number=job.part_number,
                client_id=client.client_id,
                opportunities_per_unit=10
            )

    db.flush()

    # ========================================================================
    # Production Entries (Historical Data)
    # ========================================================================

    # Get work order IDs for linking production entries
    work_order_id_list = [wo.work_order_id for wo in work_orders]

    production_entries = TestDataFactory.create_production_entries_batch(
        db,
        client_id=client.client_id,
        product_id=products[0].product_id,
        shift_id=shifts[0].shift_id,
        entered_by=supervisor.user_id,
        count=days_of_data,
        base_date=base_date,
        work_order_ids=work_order_id_list  # Link to work orders
    )

    # ========================================================================
    # Quality Entries
    # ========================================================================

    quality_entries = TestDataFactory.create_quality_entries_batch(
        db,
        work_order_id=work_orders[0].work_order_id,
        client_id=client.client_id,
        inspector_id=supervisor.user_id,
        count=days_of_data // 3,
        base_date=base_date,
        defect_rate=0.005
    )

    # Add defect details
    defect_details = []
    for qe in quality_entries[:5]:
        detail = TestDataFactory.create_defect_detail(
            db,
            quality_entry_id=qe.quality_entry_id,
            defect_count=qe.units_defective,
        )
        defect_details.append(detail)

    # ========================================================================
    # Attendance Entries
    # ========================================================================

    attendance_entries = []
    for emp in employees[:5]:  # First 5 employees
        entries = TestDataFactory.create_attendance_entries_batch(
            db,
            employee_id=emp.employee_id,
            client_id=client.client_id,
            shift_id=shifts[0].shift_id,
            count=days_of_data,
            base_date=base_date,
            attendance_rate=0.95
        )
        attendance_entries.extend(entries)

    # ========================================================================
    # Hold Entries
    # ========================================================================

    hold_entries = []
    for i, wo in enumerate(work_orders[:3]):
        hold = TestDataFactory.create_hold_entry(
            db,
            work_order_id=wo.work_order_id,
            client_id=client.client_id,
            created_by=supervisor.user_id,
            hold_reason=f"Test hold reason {i+1}",
            hold_status=HoldStatus.PENDING_HOLD_APPROVAL if i == 0 else HoldStatus.ON_HOLD,
        )
        hold_entries.append(hold)

    # ========================================================================
    # Downtime Entries
    # ========================================================================

    downtime_entries = []
    downtime_reasons = ["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "SETUP_CHANGEOVER"]
    for i in range(5):
        start_time = datetime.combine(
            base_date + timedelta(days=i * 5),
            datetime.strptime("10:00:00", "%H:%M:%S").time()
        )
        end_time = start_time + timedelta(minutes=30 + i * 10)

        dt = TestDataFactory.create_downtime_entry(
            db,
            client_id=client.client_id,
            reported_by=operator.user_id,
            downtime_reason=downtime_reasons[i % len(downtime_reasons)],
            downtime_start=start_time,
            downtime_end=end_time,
        )
        downtime_entries.append(dt)

    # ========================================================================
    # Workflow Transitions
    # ========================================================================

    transitions = []
    for wo in work_orders[:2]:
        trans = TestDataFactory.create_workflow_transition(
            db,
            work_order_id=wo.work_order_id,
            from_status="RECEIVED",
            to_status="IN_PROGRESS",
            transitioned_by=supervisor.user_id,
            client_id=client.client_id,
        )
        transitions.append(trans)

    # ========================================================================
    # Saved Filters
    # ========================================================================

    filters = []
    filter_configs = [
        ("My Production", "production", {"date_range": "last_7_days"}),
        ("Open Orders", "work_order", {"status": "RECEIVED"}),
        ("Quality Issues", "quality", {"defect_count_min": 1}),
    ]
    for name, ftype, criteria in filter_configs:
        sf = TestDataFactory.create_saved_filter(
            db,
            user_id=supervisor.user_id,
            filter_name=name,
            filter_type=ftype,
            filter_criteria=criteria,
        )
        filters.append(sf)

    db.commit()

    return {
        "client": client,
        "users": {
            "admin": admin,
            "supervisor": supervisor,
            "operator": operator,
        },
        "employees": employees,
        "products": products,
        "shifts": shifts,
        "work_orders": work_orders,
        "jobs": jobs,
        "production_entries": production_entries,
        "quality_entries": quality_entries,
        "defect_details": defect_details,
        "attendance_entries": attendance_entries,
        "hold_entries": hold_entries,
        "downtime_entries": downtime_entries,
        "transitions": transitions,
        "filters": filters,
    }


def seed_multi_tenant_data(db: Session) -> Dict[str, Any]:
    """
    Seed data for multi-tenant isolation tests.
    Creates two separate clients with their own data to test isolation.

    Args:
        db: Database session

    Returns:
        Dict with entities organized by client
    """
    TestDataFactory.reset_counters()

    result = {"clients": {}, "users": {}}

    # Create clients first, then per-client products and shifts
    clients_created = {}
    for client_suffix in ["A", "B"]:
        client_id = f"CLIENT-{client_suffix}"

        # Create client
        client = TestDataFactory.create_client(
            db,
            client_id=client_id,
            client_name=f"Test Client {client_suffix}",
            client_type=ClientType.HOURLY_RATE
        )
        clients_created[client_suffix] = client

    # Create per-client products and shifts
    product = TestDataFactory.create_product(
        db,
        client_id="CLIENT-A",
        product_code="PROD-SHARED-001",
        product_name="Shared Product"
    )

    shift = TestDataFactory.create_shift(
        db,
        client_id="CLIENT-A",
        shift_name="Shared Shift"
    )

    # Also create for CLIENT-B
    TestDataFactory.create_product(
        db,
        client_id="CLIENT-B",
        product_code="PROD-SHARED-001",
        product_name="Shared Product"
    )

    TestDataFactory.create_shift(
        db,
        client_id="CLIENT-B",
        shift_name="Shared Shift"
    )

    db.flush()

    for client_suffix in ["A", "B"]:
        client_id = f"CLIENT-{client_suffix}"
        client = clients_created[client_suffix]

        # Create supervisor for this client
        supervisor = TestDataFactory.create_user(
            db,
            username=f"supervisor_{client_suffix.lower()}",
            role="supervisor",
            client_id=client_id
        )

        # Create operator for this client
        operator = TestDataFactory.create_user(
            db,
            username=f"operator_{client_suffix.lower()}",
            role="operator",
            client_id=client_id
        )

        db.flush()

        # Create work order
        work_order = TestDataFactory.create_work_order(
            db,
            client_id=client_id,
            work_order_id=f"WO-{client_suffix}-001",
            style_model=f"STYLE-{client_suffix}"
        )

        # Create employee
        employee = TestDataFactory.create_employee(
            db,
            client_id=client_id,
            employee_name=f"Employee {client_suffix}",
            employee_code=f"EMP-{client_suffix}-001"
        )

        db.flush()

        # Create production entry
        production = TestDataFactory.create_production_entry(
            db,
            client_id=client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=supervisor.user_id,
            units_produced=1000 if client_suffix == "A" else 2000
        )

        # Create quality entry
        quality = TestDataFactory.create_quality_entry(
            db,
            work_order_id=work_order.work_order_id,
            client_id=client_id,
            inspector_id=supervisor.user_id
        )

        result["clients"][client_suffix] = {
            "client": client,
            "work_order": work_order,
            "employee": employee,
            "production": production,
            "quality": quality,
        }

        result["users"][f"supervisor_{client_suffix.lower()}"] = supervisor
        result["users"][f"operator_{client_suffix.lower()}"] = operator

    # Add shared resources to result
    result["product"] = product
    result["shift"] = shift

    # Create admin user (no client restriction)
    admin = TestDataFactory.create_user(
        db,
        username="admin_multi",
        role="admin",
        client_id=None
    )
    result["users"]["admin"] = admin

    # Create leader with access to both clients
    leader = TestDataFactory.create_user(
        db,
        username="leader_multi",
        role="leader",
        client_id="CLIENT-A,CLIENT-B"
    )
    result["users"]["leader"] = leader

    db.commit()

    return result


def cleanup_test_data(db: Session):
    """
    Clean up all test data from the database.
    Uses CASCADE-aware deletion order.

    Args:
        db: Database session
    """
    from backend.schemas import (
        WorkflowTransitionLog, FilterHistory, SavedFilter,
        DefectDetail, QualityEntry, DowntimeEntry, HoldEntry,
        AttendanceEntry, CoverageEntry, ProductionEntry,
        Job, PartOpportunities, WorkOrder,
        FloatingPool, Employee, Product, Shift, User, Client
    )

    # Delete in FK-safe order (children first)
    tables_to_clear = [
        WorkflowTransitionLog,
        FilterHistory,
        SavedFilter,
        DefectDetail,
        QualityEntry,
        DowntimeEntry,
        HoldEntry,
        AttendanceEntry,
        CoverageEntry,
        ProductionEntry,
        Job,
        PartOpportunities,
        WorkOrder,
        FloatingPool,
        Employee,
        Product,
        Shift,
        User,
        Client,
    ]

    for table in tables_to_clear:
        try:
            db.query(table).delete()
        except Exception:
            pass  # Ignore if table doesn't exist or has issues

    db.commit()
    TestDataFactory.reset_counters()
