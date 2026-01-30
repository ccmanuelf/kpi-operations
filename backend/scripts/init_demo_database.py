#!/usr/bin/env python3
"""
Initialize Demo Database
Creates tables and seeds with comprehensive demo data for platform demonstration.
Run: python -m scripts.init_demo_database
"""
import sys
import os

# Ensure backend module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine, Base, SessionLocal
from backend.tests.fixtures.seed_data import seed_multi_tenant_data, seed_comprehensive_data
from backend.tests.fixtures.factories import TestDataFactory
from backend.schemas.alert import Alert


def init_database():
    """Initialize database with schema and demo data."""
    print("=" * 60)
    print("KPI Operations Platform - Database Initialization")
    print("=" * 60)

    # Step 1: Create all tables
    print("\n[1/4] Creating database schema...")
    Base.metadata.create_all(bind=engine)
    print("  ✓ All tables created")

    # Step 2: Open session
    db = SessionLocal()

    try:
        # Step 3: Seed comprehensive multi-tenant data
        print("\n[2/4] Seeding multi-tenant demo data...")
        multi_data = seed_multi_tenant_data(db)
        print(f"  ✓ Created 2 clients (CLIENT-A, CLIENT-B)")
        print(f"  ✓ Created users: admin, leader, supervisors, operators")
        print(f"  ✓ Created employees, work orders, production entries")

        # Step 4: Add more comprehensive data for CLIENT-A
        print("\n[3/4] Adding comprehensive historical data...")

        # Reset counters to avoid conflicts
        TestDataFactory.reset_counters()

        # Get reference to existing entities
        client_a = multi_data["clients"]["A"]["client"]
        supervisor_a = multi_data["users"]["supervisor_a"]
        product = multi_data["product"]
        shift = multi_data["shift"]

        # Create additional employees for CLIENT-A
        from backend.schemas.employee import Employee
        existing_employees = db.query(Employee).filter(Employee.client_id == "CLIENT-A").all()

        if len(existing_employees) < 20:
            print("  Creating additional employees...")
            for i in range(20 - len(existing_employees)):
                emp = TestDataFactory.create_employee(
                    db,
                    client_id="CLIENT-A",
                    employee_name=f"Demo Employee {i+10}",
                    employee_code=f"EMP-A-{i+10:03d}",
                    is_floating_pool=(i >= 15)
                )

        # Create additional production entries (30 days history)
        from backend.schemas.production_entry import ProductionEntry
        existing_prod = db.query(ProductionEntry).filter(ProductionEntry.client_id == "CLIENT-A").count()

        if existing_prod < 30:
            print("  Creating historical production entries...")
            TestDataFactory.create_production_entries_batch(
                db,
                client_id="CLIENT-A",
                product_id=product.product_id,
                shift_id=shift.shift_id,
                entered_by=supervisor_a.user_id,
                count=30,
            )

        # Create additional attendance records
        from backend.schemas.attendance_entry import AttendanceEntry
        employees = db.query(Employee).filter(Employee.client_id == "CLIENT-A").all()
        existing_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.client_id == "CLIENT-A").count()

        if existing_attendance < 100:
            print("  Creating attendance history...")
            for emp in employees[:5]:
                TestDataFactory.create_attendance_entries_batch(
                    db,
                    employee_id=emp.employee_id,
                    client_id="CLIENT-A",
                    shift_id=shift.shift_id,
                    count=14,
                    attendance_rate=0.92
                )

        # Create alerts
        from backend.schemas.alert import Alert
        existing_alerts = db.query(Alert).count()

        if existing_alerts < 5:
            print("  Creating demo alerts...")
            from datetime import datetime
            alert_data = [
                ("Efficiency Below Target", "efficiency", "warning", "CLIENT-A"),
                ("OTD Critical", "otd", "critical", "CLIENT-A"),
                ("Quality PPM Elevated", "quality", "warning", "CLIENT-B"),
                ("Absenteeism High", "absenteeism", "critical", "CLIENT-B"),
                ("Equipment Downtime", "availability", "info", "CLIENT-A"),
            ]
            for title, category, severity, client_id in alert_data:
                alert = Alert(
                    client_id=client_id,
                    alert_type="kpi_threshold",
                    severity=severity,
                    category=category,
                    title=title,
                    message=f"Demo alert for {category} monitoring",
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(alert)

        db.commit()
        print("  ✓ Historical data created")

        # Step 5: Summary
        print("\n[4/4] Verifying data...")

        from backend.schemas.client import Client
        from backend.schemas.user import User
        from backend.schemas.work_order import WorkOrder
        from backend.schemas.quality_entry import QualityEntry
        from backend.schemas.downtime_entry import DowntimeEntry

        counts = {
            "Clients": db.query(Client).count(),
            "Users": db.query(User).count(),
            "Employees": db.query(Employee).count(),
            "Work Orders": db.query(WorkOrder).count(),
            "Production Entries": db.query(ProductionEntry).count(),
            "Quality Entries": db.query(QualityEntry).count(),
            "Attendance Entries": db.query(AttendanceEntry).count(),
            "Alerts": db.query(Alert).count(),
        }

        print("\n" + "=" * 60)
        print("Database Initialization Complete!")
        print("=" * 60)
        print("\nData Summary:")
        for entity, count in counts.items():
            print(f"  {entity}: {count}")

        print("\n" + "-" * 60)
        print("Demo Login Credentials:")
        print("-" * 60)
        print("  Admin:      admin_multi / TestPass123!")
        print("  Leader:     leader_multi / TestPass123!")
        print("  Supervisor: supervisor_a / TestPass123!")
        print("  Operator:   operator_a / TestPass123!")
        print("-" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
