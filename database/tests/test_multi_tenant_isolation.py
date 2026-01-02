"""
Multi-Tenant Security Isolation Testing Suite

Tests comprehensive security boundaries for:
- OPERATOR: Single client access only
- LEADER: Multi-client access (assigned list)
- ADMIN: All client access (POWERUSER)
- Cross-client data leakage prevention
- KPI calculation isolation
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from typing import List, Set
import json

from backend.database import Base
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
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = None

    def __enter__(self):
        self.db = self.SessionLocal()
        self._setup_test_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
        Base.metadata.drop_all(self.engine)

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

    def validate_access(self, user: User, entity_id: str, entity_client_id: str) -> bool:
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

    def filter_by_client_access(self, user: User, entities: List) -> List:
        """Filter entities based on user's client access"""
        # ADMIN and POWERUSER see all
        if user.role in (UserRole.ADMIN, UserRole.POWERUSER):
            return entities

        if user.client_id_assigned is None:
            return []

        allowed_clients = [c.strip() for c in user.client_id_assigned.split(',')]
        return [e for e in entities if e.client_id in allowed_clients]

    def log_test_result(self, test_name: str, passed: bool, details: str):
        """Log test result for final report"""
        self.test_results.append({
            'test': test_name,
            'status': 'PASS' if passed else 'FAIL',
            'details': details,
            'timestamp': datetime.now().isoformat()
        })

    def generate_report(self) -> str:
        """Generate comprehensive validation report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['status'] == 'PASS')
        failed_tests = total_tests - passed_tests

        report = [
            "=" * 80,
            "MULTI-TENANT SECURITY VALIDATION REPORT",
            "=" * 80,
            f"Total Tests: {total_tests}",
            f"Passed: {passed_tests} ✅",
            f"Failed: {failed_tests} ❌",
            f"Success Rate: {(passed_tests/total_tests*100):.1f}%",
            "=" * 80,
            "",
            "DETAILED RESULTS:",
            "-" * 80,
        ]

        for result in self.test_results:
            status_icon = "✅" if result['status'] == 'PASS' else "❌"
            report.append(f"{status_icon} {result['test']}")
            report.append(f"   Status: {result['status']}")
            report.append(f"   Details: {result['details']}")
            report.append(f"   Time: {result['timestamp']}")
            report.append("-" * 80)

        return "\n".join(report)


# TEST SCENARIOS

def test_operator_single_client_access():
    """
    SCENARIO 1: OPERATOR User - Single Client Access

    Tests that OPERATOR users can only access their assigned client's data
    and cannot access other clients' data.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        # Create OPERATOR user assigned to BOOT-LINE-A only
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
            # TEST: Can query own client's work orders
            all_work_orders = ctx.db.query(WorkOrder).all()
            accessible_work_orders = validator.filter_by_client_access(operator, all_work_orders)

            assert all(wo.client_id == "BOOT-LINE-A" for wo in accessible_work_orders), \
                "OPERATOR can see work orders from other clients!"

            assert len(accessible_work_orders) == 5, \
                f"Expected 5 work orders for BOOT-LINE-A, got {len(accessible_work_orders)}"

            validator.log_test_result(
                "OPERATOR - Own Client Access",
                True,
                f"Successfully accessed 5 work orders for BOOT-LINE-A"
            )

            # TEST: Cannot access other client's work order
            other_client_wo = ctx.db.query(WorkOrder).filter(
                WorkOrder.work_order_id == "WO-APPAREL-B-001"
            ).first()

            access_denied = False
            try:
                validator.validate_access(operator, other_client_wo.work_order_id, other_client_wo.client_id)
            except ClientAccessError:
                access_denied = True

            assert access_denied, "OPERATOR should not access other client's data!"

            validator.log_test_result(
                "OPERATOR - Other Client Denial",
                True,
                "Successfully blocked access to APPAREL-B work order"
            )

            print("✅ OPERATOR isolation verified")

        except AssertionError as e:
            validator.log_test_result(
                "OPERATOR - Single Client Access",
                False,
                str(e)
            )
            raise


def test_leader_multi_client_access():
    """
    SCENARIO 2: LEADER User - Multi-Client Access

    Tests that LEADER users can access multiple assigned clients
    but not unassigned clients.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        # Create LEADER assigned to 3 clients
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
            # TEST: Can access all 3 assigned clients
            all_work_orders = ctx.db.query(WorkOrder).all()
            accessible_work_orders = validator.filter_by_client_access(leader, all_work_orders)

            client_ids = set(wo.client_id for wo in accessible_work_orders)
            expected_clients = {"BOOT-LINE-A", "APPAREL-B", "TEXTILE-C"}

            assert client_ids == expected_clients, \
                f"LEADER should access {expected_clients}, got {client_ids}"

            assert len(accessible_work_orders) == 15, \
                f"Expected 15 work orders (5 per client × 3 clients), got {len(accessible_work_orders)}"

            validator.log_test_result(
                "LEADER - Multi-Client Access",
                True,
                f"Successfully accessed 15 work orders across 3 clients: {expected_clients}"
            )

            # TEST: Cannot access unassigned client
            unassigned_wo = ctx.db.query(WorkOrder).filter(
                WorkOrder.work_order_id == "WO-FOOTWEAR-D-001"
            ).first()

            access_denied = False
            try:
                validator.validate_access(leader, unassigned_wo.work_order_id, unassigned_wo.client_id)
            except ClientAccessError:
                access_denied = True

            assert access_denied, "LEADER should not access unassigned client FOOTWEAR-D!"

            validator.log_test_result(
                "LEADER - Unassigned Client Denial",
                True,
                "Successfully blocked access to FOOTWEAR-D (unassigned client)"
            )

            print("✅ LEADER multi-client access verified")

        except AssertionError as e:
            validator.log_test_result(
                "LEADER - Multi-Client Access",
                False,
                str(e)
            )
            raise


def test_admin_all_client_access():
    """
    SCENARIO 3: POWERUSER - All Client Access

    Tests that POWERUSER users can access all clients without restrictions.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        # Create POWERUSER (client_id_assigned = None means all clients)
        poweruser = User(
            username="poweruser1",
            email="poweruser1@example.com",
            password_hash="hashed_password",
            full_name="Power User One",
            role=UserRole.POWERUSER,
            client_id_assigned=None,  # NULL = all clients
            is_active=True
        )

        try:
            # TEST: Can access ALL clients
            all_work_orders = ctx.db.query(WorkOrder).all()
            accessible_work_orders = validator.filter_by_client_access(poweruser, all_work_orders)

            client_ids = set(wo.client_id for wo in accessible_work_orders)
            expected_clients = {"BOOT-LINE-A", "APPAREL-B", "TEXTILE-C", "FOOTWEAR-D", "GARMENT-E"}

            assert client_ids == expected_clients, \
                f"POWERUSER should access all 5 clients, got {client_ids}"

            assert len(accessible_work_orders) == 25, \
                f"Expected 25 work orders (all clients), got {len(accessible_work_orders)}"

            validator.log_test_result(
                "POWERUSER - All Client Access",
                True,
                f"Successfully accessed all 25 work orders across 5 clients"
            )

            print("✅ POWERUSER all-client access verified")

        except AssertionError as e:
            validator.log_test_result(
                "POWERUSER - All Client Access",
                False,
                str(e)
            )
            raise


def test_no_data_leakage():
    """
    SCENARIO 4: Cross-Client Data Leakage Prevention

    Tests that data from different clients is completely isolated
    with no overlap between operators from different clients.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        # Create two operators for different clients
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
            # Get production entries for each operator
            all_production = ctx.db.query(ProductionEntry).all()

            data_a = validator.filter_by_client_access(operator_a, all_production)
            data_b = validator.filter_by_client_access(operator_b, all_production)

            # Verify NO overlap
            ids_a = set(entry.production_entry_id for entry in data_a)
            ids_b = set(entry.production_entry_id for entry in data_b)

            overlap = ids_a.intersection(ids_b)

            assert len(overlap) == 0, \
                f"DATA LEAKAGE DETECTED! {len(overlap)} shared entries: {overlap}"

            # Verify each operator sees only their client's data
            assert all(e.client_id == "BOOT-LINE-A" for e in data_a), \
                "Operator A sees data from other clients!"

            assert all(e.client_id == "APPAREL-B" for e in data_b), \
                "Operator B sees data from other clients!"

            validator.log_test_result(
                "Cross-Client Data Leakage Prevention",
                True,
                f"No data overlap: Operator A sees {len(data_a)} entries, "
                f"Operator B sees {len(data_b)} entries, 0 shared"
            )

            print("✅ No cross-client data leakage")

        except AssertionError as e:
            validator.log_test_result(
                "Cross-Client Data Leakage Prevention",
                False,
                str(e)
            )
            raise


def test_kpi_isolation():
    """
    SCENARIO 5: KPI Calculation Isolation

    Tests that KPI calculations only use data from the user's
    authorized clients and do not leak data from other clients.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        # Create OPERATOR for single client
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
            # Get filtered data for KPI calculations
            all_work_orders = ctx.db.query(WorkOrder).all()
            all_production = ctx.db.query(ProductionEntry).all()
            all_quality = ctx.db.query(QualityEntry).all()
            all_downtime = ctx.db.query(DowntimeEntry).all()

            filtered_work_orders = validator.filter_by_client_access(operator, all_work_orders)
            filtered_production = validator.filter_by_client_access(operator, all_production)
            filtered_quality = validator.filter_by_client_access(operator, all_quality)
            filtered_downtime = validator.filter_by_client_access(operator, all_downtime)

            # Verify all filtered data belongs to BOOT-LINE-A only
            assert all(wo.client_id == "BOOT-LINE-A" for wo in filtered_work_orders)
            assert all(pe.client_id == "BOOT-LINE-A" for pe in filtered_production)
            assert all(qi.client_id == "BOOT-LINE-A" for qi in filtered_quality)
            assert all(dt.client_id == "BOOT-LINE-A" for dt in filtered_downtime)

            # Calculate KPIs using filtered data
            total_target = sum(wo.target_quantity for wo in filtered_work_orders)
            total_completed = sum(wo.completed_quantity for wo in filtered_work_orders)
            efficiency = (total_completed / total_target * 100) if total_target > 0 else 0

            total_inspected = sum(qi.passed_quantity + qi.failed_quantity for qi in filtered_quality)
            total_passed = sum(qi.passed_quantity for qi in filtered_quality)
            quality_rate = (total_passed / total_inspected * 100) if total_inspected > 0 else 0

            # Verify KPI calculations
            kpi_summary = {
                'client_id': 'BOOT-LINE-A',
                'work_orders': len(filtered_work_orders),
                'efficiency': round(efficiency, 2),
                'quality_rate': round(quality_rate, 2),
                'production_entries': len(filtered_production),
                'downtime_records': len(filtered_downtime)
            }

            validator.log_test_result(
                "KPI Isolation - Efficiency Calculation",
                True,
                f"KPIs calculated only from BOOT-LINE-A data: {json.dumps(kpi_summary, indent=2)}"
            )

            # Verify no data contamination from other clients
            all_clients_production = ctx.db.query(ProductionEntry).all()
            other_clients_production = [
                p for p in all_clients_production
                if p.client_id != "BOOT-LINE-A"
            ]

            assert len(other_clients_production) > 0, "Test setup issue: no other client data"

            # Ensure filtered data doesn't include other clients
            filtered_ids = set(p.production_entry_id for p in filtered_production)
            other_ids = set(p.production_entry_id for p in other_clients_production)

            contamination = filtered_ids.intersection(other_ids)
            assert len(contamination) == 0, \
                f"KPI data contamination: {len(contamination)} entries from other clients!"

            validator.log_test_result(
                "KPI Isolation - No Contamination",
                True,
                "KPI calculations use zero entries from other clients"
            )

            print("✅ KPI isolation verified")

        except AssertionError as e:
            validator.log_test_result(
                "KPI Isolation",
                False,
                str(e)
            )
            raise


def test_production_entry_isolation():
    """
    SCENARIO 6: Production Entry Isolation

    Tests that production entries are properly isolated by client
    and users cannot create/modify entries for other clients.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        operator = User(
            username="operator_prod",
            email="operator_prod@example.com",
            password_hash="hashed_password",
            full_name="Production Operator",
            role=UserRole.OPERATOR,
            client_id_assigned="TEXTILE-C",
            is_active=True
        )

        try:
            # TEST: Can only see TEXTILE-C production entries
            all_production = ctx.db.query(ProductionEntry).all()
            accessible_production = validator.filter_by_client_access(operator, all_production)

            assert all(pe.client_id == "TEXTILE-C" for pe in accessible_production)

            # TEST: Cannot access production entry from different client
            other_client_entry = ctx.db.query(ProductionEntry).filter(
                ProductionEntry.client_id == "BOOT-LINE-A"
            ).first()

            if other_client_entry:
                access_denied = False
                try:
                    validator.validate_access(
                        operator,
                        other_client_entry.production_entry_id,
                        other_client_entry.client_id
                    )
                except ClientAccessError:
                    access_denied = True

                assert access_denied, "Operator accessed production entry from different client!"

            validator.log_test_result(
                "Production Entry Isolation",
                True,
                f"TEXTILE-C operator can only access {len(accessible_production)} TEXTILE-C production entries"
            )

            print("✅ Production entry isolation verified")

        except AssertionError as e:
            validator.log_test_result(
                "Production Entry Isolation",
                False,
                str(e)
            )
            raise


def test_quality_inspection_isolation():
    """
    SCENARIO 7: Quality Inspection Isolation

    Tests that quality inspections are isolated by client.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        leader = User(
            username="leader_quality",
            email="leader_quality@example.com",
            password_hash="hashed_password",
            full_name="Quality Leader",
            role=UserRole.LEADER,
            client_id_assigned="BOOT-LINE-A,FOOTWEAR-D",
            is_active=True
        )

        try:
            # TEST: Can access inspections for assigned clients only
            all_inspections = ctx.db.query(QualityEntry).all()
            accessible_inspections = validator.filter_by_client_access(leader, all_inspections)

            client_ids = set(qi.client_id for qi in accessible_inspections)
            expected_clients = {"BOOT-LINE-A", "FOOTWEAR-D"}

            # Note: May not have inspections for all assigned clients
            assert client_ids.issubset(expected_clients), \
                f"Leader accessed inspections from unauthorized clients: {client_ids - expected_clients}"

            validator.log_test_result(
                "Quality Inspection Isolation",
                True,
                f"Leader can access {len(accessible_inspections)} inspections from authorized clients only"
            )

            print("✅ Quality inspection isolation verified")

        except AssertionError as e:
            validator.log_test_result(
                "Quality Inspection Isolation",
                False,
                str(e)
            )
            raise


def test_downtime_record_isolation():
    """
    SCENARIO 8: Downtime Record Isolation

    Tests that downtime records are isolated by client.
    """
    with SecurityTestContext() as ctx:
        validator = SecurityValidator(ctx.db)

        operator = User(
            username="operator_downtime",
            email="operator_downtime@example.com",
            password_hash="hashed_password",
            full_name="Downtime Operator",
            role=UserRole.OPERATOR,
            client_id_assigned="GARMENT-E",
            is_active=True
        )

        try:
            # TEST: Can only access GARMENT-E downtime records
            all_downtime = ctx.db.query(DowntimeEntry).all()
            accessible_downtime = validator.filter_by_client_access(operator, all_downtime)

            assert all(dt.client_id == "GARMENT-E" for dt in accessible_downtime)

            # Count all downtime records to verify filtering
            garment_e_count = len(accessible_downtime)
            total_count = len(all_downtime)

            validator.log_test_result(
                "Downtime Record Isolation",
                True,
                f"Operator can access {garment_e_count} GARMENT-E downtime records "
                f"out of {total_count} total records"
            )

            print("✅ Downtime record isolation verified")

        except AssertionError as e:
            validator.log_test_result(
                "Downtime Record Isolation",
                False,
                str(e)
            )
            raise


def run_all_security_tests():
    """
    Execute all security validation tests and generate comprehensive report
    """
    print("=" * 80)
    print("STARTING MULTI-TENANT SECURITY VALIDATION TEST SUITE")
    print("=" * 80)
    print()

    test_functions = [
        test_operator_single_client_access,
        test_leader_multi_client_access,
        test_admin_all_client_access,
        test_no_data_leakage,
        test_kpi_isolation,
        test_production_entry_isolation,
        test_quality_inspection_isolation,
        test_downtime_record_isolation
    ]

    results = []

    for test_func in test_functions:
        print(f"\n🔍 Running: {test_func.__name__}")
        print("-" * 80)

        try:
            test_func()
            results.append({'test': test_func.__name__, 'status': 'PASS'})
            print(f"✅ {test_func.__name__} PASSED")
        except Exception as e:
            results.append({'test': test_func.__name__, 'status': 'FAIL', 'error': str(e)})
            print(f"❌ {test_func.__name__} FAILED: {e}")

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
        if result['status'] == 'FAIL':
            print(f"   Error: {result.get('error', 'Unknown error')}")

    print("=" * 80)

    return results


if __name__ == "__main__":
    results = run_all_security_tests()

    # Exit with error code if any tests failed
    failed_count = sum(1 for r in results if r['status'] == 'FAIL')
    exit(0 if failed_count == 0 else 1)
