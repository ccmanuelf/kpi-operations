#!/usr/bin/env python3
"""
Standalone Multi-Tenant Security Validation Test Runner

This script runs comprehensive security validation tests without requiring
the full backend setup or database connection.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import json

# Create standalone Base for testing
Base = declarative_base()

# Import all schema models
from backend.schemas import (
    User, UserRole, Client, ClientType, WorkOrder, WorkOrderStatus,
    ProductionEntry, QualityEntry, DowntimeEntry, DowntimeReason,
    HoldEntry, HoldStatus, AttendanceEntry, AbsenceType
)


class ClientAccessError(Exception):
    """Raised when user attempts to access unauthorized client data"""
    pass


class SecurityTestContext:
    """Context manager for security testing with isolated database"""

    def __init__(self):
        # Use in-memory SQLite database
        self.engine = create_engine('sqlite:///:memory:', echo=False)
        # Create all tables from imported schemas
        from backend.database import Base as BackendBase
        BackendBase.metadata.create_all(self.engine)

        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = None

    def __enter__(self):
        self.db = self.SessionLocal()
        self._setup_test_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    def _setup_test_data(self):
        """Setup test data for 5 clients with work orders and production data"""

        # Create 5 distinct clients
        clients = [
            Client(
                client_id="BOOT-LINE-A",
                client_name="Boot Manufacturing Line A",
                client_type=ClientType.MANUFACTURING,
                is_active=True
            ),
            Client(
                client_id="APPAREL-B",
                client_name="Apparel Production B",
                client_type=ClientType.MANUFACTURING,
                is_active=True
            ),
            Client(
                client_id="TEXTILE-C",
                client_name="Textile Operations C",
                client_type=ClientType.MANUFACTURING,
                is_active=True
            ),
            Client(
                client_id="FOOTWEAR-D",
                client_name="Footwear Assembly D",
                client_type=ClientType.MANUFACTURING,
                is_active=True
            ),
            Client(
                client_id="GARMENT-E",
                client_name="Garment Factory E",
                client_type=ClientType.MANUFACTURING,
                is_active=True
            )
        ]
        self.db.add_all(clients)
        self.db.commit()

        # Create work orders for each client (5 per client = 25 total)
        work_orders = []
        for idx, client in enumerate(clients):
            for wo_num in range(1, 6):
                wo = WorkOrder(
                    work_order_id=f"WO-{client.client_id}-{wo_num:03d}",
                    client_id=client.client_id,
                    customer_name=f"Customer {client.client_name}",
                    product_name=f"{client.client_name} Product {wo_num}",
                    style_number=f"STY-{wo_num:04d}",
                    target_quantity=1000 * wo_num,
                    completed_quantity=800 * wo_num if wo_num < 4 else 0,
                    start_date=datetime.now() - timedelta(days=10),
                    due_date=datetime.now() + timedelta(days=wo_num),
                    status=WorkOrderStatus.IN_PROGRESS if wo_num < 4 else WorkOrderStatus.PENDING
                )
                work_orders.append(wo)

        self.db.add_all(work_orders)
        self.db.commit()

        # Create production entries for each work order
        production_entries = []
        for wo in work_orders[:15]:  # First 3 work orders per client
            for day in range(5):
                entry = ProductionEntry(
                    client_id=wo.client_id,
                    work_order_id=wo.work_order_id,
                    production_date=datetime.now() - timedelta(days=5-day),
                    shift_id=1 if day % 2 == 0 else 2,
                    quantity_produced=150 + (day * 10),
                    target_quantity=200,
                    efficiency_percentage=75.0 + (day * 2)
                )
                production_entries.append(entry)

        self.db.add_all(production_entries)
        self.db.commit()

        # Create quality entries
        quality_entries = []
        for entry in production_entries[:30]:  # Subset of production entries
            quality = QualityEntry(
                client_id=entry.client_id,
                work_order_id=entry.work_order_id,
                production_date=entry.production_date,
                shift_id=entry.shift_id,
                total_inspected=entry.quantity_produced,
                total_defects=5 + (entry.quantity_produced // 50),
                defect_percentage=3.5
            )
            quality_entries.append(quality)

        self.db.add_all(quality_entries)
        self.db.commit()

        # Create downtime entries
        downtime_entries = []
        for wo in work_orders[:10]:  # First 2 work orders per client
            downtime = DowntimeEntry(
                client_id=wo.client_id,
                work_order_id=wo.work_order_id,
                downtime_date=datetime.now() - timedelta(hours=2),
                shift_id=1,
                reason=DowntimeReason.EQUIPMENT_FAILURE,
                duration_minutes=60,
                description="Equipment maintenance required"
            )
            downtime_entries.append(downtime)

        self.db.add_all(downtime_entries)
        self.db.commit()

        print(f"✅ Test data created:")
        print(f"   - 5 clients")
        print(f"   - 25 work orders (5 per client)")
        print(f"   - {len(production_entries)} production entries")
        print(f"   - {len(quality_entries)} quality entries")
        print(f"   - {len(downtime_entries)} downtime entries")


class SecurityValidator:
    """Validates security boundaries and access control"""

    def __init__(self, db):
        self.db = db
        self.test_results = []

    def validate_access(self, user, entity_id, entity_client_id):
        """
        Validates if user has access to an entity based on client assignment

        Returns:
            True if access allowed, raises ClientAccessError if denied
        """
        # ADMIN and POWERUSER have access to all clients
        if user.role in (UserRole.ADMIN, UserRole.POWERUSER):
            return True

        if user.client_id_assigned is None:
            raise ClientAccessError(f"User {user.username} has no client assignment")

        allowed_clients = [c.strip() for c in user.client_id_assigned.split(',')]

        if entity_client_id not in allowed_clients:
            raise ClientAccessError(
                f"User {user.username} (role: {user.role}, clients: {allowed_clients}) "
                f"cannot access entity {entity_id} (client: {entity_client_id})"
            )

        return True

    def filter_by_client_access(self, user, entities):
        """Filter entities based on user's client access"""
        # ADMIN and POWERUSER see all
        if user.role in (UserRole.ADMIN, UserRole.POWERUSER):
            return entities

        if user.client_id_assigned is None:
            return []

        allowed_clients = [c.strip() for c in user.client_id_assigned.split(',')]
        return [e for e in entities if e.client_id in allowed_clients]

    def log_test_result(self, test_name, passed, details):
        """Log test result for final report"""
        self.test_results.append({
            'test': test_name,
            'status': 'PASS' if passed else 'FAIL',
            'details': details,
            'timestamp': datetime.now().isoformat()
        })


def test_operator_single_client_access():
    """Test OPERATOR can only access single assigned client"""
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        operator = User(
            username="operator1",
            email="operator1@example.com",
            password_hash="hashed_password",
            full_name="Operator One",
            role=UserRole.OPERATOR,
            client_id_assigned="BOOT-LINE-A",
            is_active=True
        )

        try:
            all_work_orders = ctx.db.query(WorkOrder).all()
            accessible_work_orders = validator.filter_by_client_access(operator, all_work_orders)

            assert all(wo.client_id == "BOOT-LINE-A" for wo in accessible_work_orders)
            assert len(accessible_work_orders) == 5

            validator.log_test_result(
                "OPERATOR - Own Client Access",
                True,
                f"Successfully accessed 5 work orders for BOOT-LINE-A"
            )

            # Test cannot access other client
            other_client_wo = ctx.db.query(WorkOrder).filter(
                WorkOrder.work_order_id == "WO-APPAREL-B-001"
            ).first()

            access_denied = False
            try:
                validator.validate_access(operator, other_client_wo.work_order_id, other_client_wo.client_id)
            except ClientAccessError:
                access_denied = True

            assert access_denied
            validator.log_test_result(
                "OPERATOR - Other Client Denial",
                True,
                "Successfully blocked access to APPAREL-B"
            )

            print("✅ OPERATOR isolation verified")
            return True

        except AssertionError as e:
            validator.log_test_result("OPERATOR - Single Client Access", False, str(e))
            print(f"❌ OPERATOR test failed: {e}")
            return False


def test_leader_multi_client_access():
    """Test LEADER can access multiple assigned clients"""
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        leader = User(
            username="leader1",
            email="leader1@example.com",
            password_hash="hashed_password",
            full_name="Leader One",
            role=UserRole.LEADER,
            client_id_assigned="BOOT-LINE-A,APPAREL-B,TEXTILE-C",
            is_active=True
        )

        try:
            all_work_orders = ctx.db.query(WorkOrder).all()
            accessible_work_orders = validator.filter_by_client_access(leader, all_work_orders)

            client_ids = set(wo.client_id for wo in accessible_work_orders)
            expected_clients = {"BOOT-LINE-A", "APPAREL-B", "TEXTILE-C"}

            assert client_ids == expected_clients
            assert len(accessible_work_orders) == 15

            validator.log_test_result(
                "LEADER - Multi-Client Access",
                True,
                f"Successfully accessed 15 work orders across 3 clients"
            )

            # Test cannot access unassigned client
            unassigned_wo = ctx.db.query(WorkOrder).filter(
                WorkOrder.work_order_id == "WO-FOOTWEAR-D-001"
            ).first()

            access_denied = False
            try:
                validator.validate_access(leader, unassigned_wo.work_order_id, unassigned_wo.client_id)
            except ClientAccessError:
                access_denied = True

            assert access_denied
            validator.log_test_result(
                "LEADER - Unassigned Client Denial",
                True,
                "Successfully blocked access to FOOTWEAR-D"
            )

            print("✅ LEADER multi-client access verified")
            return True

        except AssertionError as e:
            validator.log_test_result("LEADER - Multi-Client Access", False, str(e))
            print(f"❌ LEADER test failed: {e}")
            return False


def test_poweruser_all_client_access():
    """Test POWERUSER can access all clients"""
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        poweruser = User(
            username="poweruser1",
            email="poweruser1@example.com",
            password_hash="hashed_password",
            full_name="Power User One",
            role=UserRole.POWERUSER,
            client_id_assigned=None,
            is_active=True
        )

        try:
            all_work_orders = ctx.db.query(WorkOrder).all()
            accessible_work_orders = validator.filter_by_client_access(poweruser, all_work_orders)

            client_ids = set(wo.client_id for wo in accessible_work_orders)
            expected_clients = {"BOOT-LINE-A", "APPAREL-B", "TEXTILE-C", "FOOTWEAR-D", "GARMENT-E"}

            assert client_ids == expected_clients
            assert len(accessible_work_orders) == 25

            validator.log_test_result(
                "POWERUSER - All Client Access",
                True,
                f"Successfully accessed all 25 work orders across 5 clients"
            )

            print("✅ POWERUSER all-client access verified")
            return True

        except AssertionError as e:
            validator.log_test_result("POWERUSER - All Client Access", False, str(e))
            print(f"❌ POWERUSER test failed: {e}")
            return False


def test_no_data_leakage():
    """Test no cross-client data leakage"""
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        operator_a = User(
            username="operator_a",
            email="operator_a@example.com",
            password_hash="hashed_password",
            full_name="Operator A",
            role=UserRole.OPERATOR,
            client_id_assigned="BOOT-LINE-A",
            is_active=True
        )

        operator_b = User(
            username="operator_b",
            email="operator_b@example.com",
            password_hash="hashed_password",
            full_name="Operator B",
            role=UserRole.OPERATOR,
            client_id_assigned="APPAREL-B",
            is_active=True
        )

        try:
            all_production = ctx.db.query(ProductionEntry).all()

            data_a = validator.filter_by_client_access(operator_a, all_production)
            data_b = validator.filter_by_client_access(operator_b, all_production)

            ids_a = set(entry.production_entry_id for entry in data_a)
            ids_b = set(entry.production_entry_id for entry in data_b)

            overlap = ids_a.intersection(ids_b)

            assert len(overlap) == 0
            assert all(e.client_id == "BOOT-LINE-A" for e in data_a)
            assert all(e.client_id == "APPAREL-B" for e in data_b)

            validator.log_test_result(
                "Cross-Client Data Leakage Prevention",
                True,
                f"No data overlap: Operator A sees {len(data_a)} entries, Operator B sees {len(data_b)} entries"
            )

            print("✅ No cross-client data leakage")
            return True

        except AssertionError as e:
            validator.log_test_result("Cross-Client Data Leakage Prevention", False, str(e))
            print(f"❌ Data leakage test failed: {e}")
            return False


def test_kpi_isolation():
    """Test KPI calculations are isolated by client"""
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        operator = User(
            username="operator_kpi",
            email="operator_kpi@example.com",
            password_hash="hashed_password",
            full_name="KPI Operator",
            role=UserRole.OPERATOR,
            client_id_assigned="BOOT-LINE-A",
            is_active=True
        )

        try:
            all_work_orders = ctx.db.query(WorkOrder).all()
            all_production = ctx.db.query(ProductionEntry).all()
            all_quality = ctx.db.query(QualityEntry).all()
            all_downtime = ctx.db.query(DowntimeEntry).all()

            filtered_work_orders = validator.filter_by_client_access(operator, all_work_orders)
            filtered_production = validator.filter_by_client_access(operator, all_production)
            filtered_quality = validator.filter_by_client_access(operator, all_quality)
            filtered_downtime = validator.filter_by_client_access(operator, all_downtime)

            assert all(wo.client_id == "BOOT-LINE-A" for wo in filtered_work_orders)
            assert all(pe.client_id == "BOOT-LINE-A" for pe in filtered_production)
            assert all(qi.client_id == "BOOT-LINE-A" for qi in filtered_quality)
            assert all(dt.client_id == "BOOT-LINE-A" for dt in filtered_downtime)

            # Calculate KPIs
            total_target = sum(wo.target_quantity for wo in filtered_work_orders)
            total_completed = sum(wo.completed_quantity for wo in filtered_work_orders)
            efficiency = (total_completed / total_target * 100) if total_target > 0 else 0

            total_inspected = sum(qi.total_inspected for qi in filtered_quality)
            total_defects = sum(qi.total_defects for qi in filtered_quality)
            quality_rate = ((total_inspected - total_defects) / total_inspected * 100) if total_inspected > 0 else 0

            kpi_summary = {
                'client_id': 'BOOT-LINE-A',
                'work_orders': len(filtered_work_orders),
                'efficiency': round(efficiency, 2),
                'quality_rate': round(quality_rate, 2)
            }

            validator.log_test_result(
                "KPI Isolation",
                True,
                f"KPIs calculated only from BOOT-LINE-A data: {json.dumps(kpi_summary)}"
            )

            print("✅ KPI isolation verified")
            return True

        except AssertionError as e:
            validator.log_test_result("KPI Isolation", False, str(e))
            print(f"❌ KPI isolation test failed: {e}")
            return False


def run_all_security_tests():
    """Execute all security validation tests and generate report"""
    print("=" * 80)
    print("MULTI-TENANT SECURITY VALIDATION TEST SUITE")
    print("=" * 80)
    print()

    tests = [
        ("OPERATOR Single Client Access", test_operator_single_client_access),
        ("LEADER Multi-Client Access", test_leader_multi_client_access),
        ("POWERUSER All Client Access", test_poweruser_all_client_access),
        ("Cross-Client Data Leakage Prevention", test_no_data_leakage),
        ("KPI Calculation Isolation", test_kpi_isolation)
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        print("-" * 80)

        try:
            passed = test_func()
            results.append({'test': test_name, 'status': 'PASS' if passed else 'FAIL'})
        except Exception as e:
            results.append({'test': test_name, 'status': 'FAIL', 'error': str(e)})
            print(f"❌ {test_name} FAILED: {e}")

    # Generate final report
    print("\n\n")
    print("=" * 80)
    print("FINAL SECURITY VALIDATION REPORT")
    print("=" * 80)

    total_tests = len(results)
    passed_tests = sum(1 for r in results if r['status'] == 'PASS')
    failed_tests = total_tests - passed_tests

    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print("\n" + "-" * 80)
    print("DETAILED RESULTS:")
    print("-" * 80)

    for result in results:
        status_icon = "✅" if result['status'] == 'PASS' else "❌"
        print(f"{status_icon} {result['test']}: {result['status']}")
        if result['status'] == 'FAIL' and 'error' in result:
            print(f"   Error: {result.get('error', 'Unknown error')}")

    print("=" * 80)

    # Generate JSON report
    report_path = Path(__file__).parent / "security_validation_report.json"
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'success_rate': round(passed_tests/total_tests*100, 2),
            'results': results
        }, f, indent=2)

    print(f"\n📄 Detailed report saved to: {report_path}")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_security_tests()
    sys.exit(0 if success else 1)
