"""
Test Fixtures and Sample Data
Provides reusable test data for all test scenarios
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import csv
import io


class TestDataFixtures:
    """Centralized test data factory"""

    @staticmethod
    def perfect_production_entry():
        """Production entry with all fields present (ideal scenario)"""
        return {
            "production_entry_id": "PROD-TEST-PERFECT-001",
            "work_order_id": "WO-2025-001",
            "client_id": "BOOT-LINE-A",
            "shift_date": date(2025, 12, 15),
            "shift_type": "SHIFT_1ST",
            "units_produced": 100,
            "units_defective": 2,
            "run_time_hours": Decimal("8.5"),
            "employees_assigned": 10,
            "employees_present": 10,
            "data_collector_id": "USR-001",
            "entry_method": "MANUAL_ENTRY",
            "created_by": "USR-001",
            "ideal_cycle_time": Decimal("0.25")  # From work order
        }

    @staticmethod
    def missing_ideal_cycle_time_entry():
        """Production entry missing ideal_cycle_time (inference required)"""
        return {
            "production_entry_id": "PROD-TEST-INFERENCE-001",
            "work_order_id": "WO-2025-002",
            "client_id": "BOOT-LINE-A",
            "shift_date": date(2025, 12, 15),
            "shift_type": "SHIFT_1ST",
            "units_produced": 100,
            "units_defective": 0,
            "run_time_hours": Decimal("8.5"),
            "employees_assigned": 10,
            "data_collector_id": "USR-001",
            "entry_method": "MANUAL_ENTRY",
            "created_by": "USR-001",
            "ideal_cycle_time": None  # MISSING - needs inference
        }

    @staticmethod
    def missing_employees_assigned_entry():
        """Production entry missing employees_assigned (use shift default)"""
        return {
            "production_entry_id": "PROD-TEST-NOEMPLOYEES-001",
            "work_order_id": "WO-2025-003",
            "client_id": "BOOT-LINE-A",
            "shift_date": date(2025, 12, 15),
            "shift_type": "SHIFT_1ST",
            "units_produced": 100,
            "run_time_hours": Decimal("8.5"),
            "employees_assigned": None,  # MISSING - use default
            "data_collector_id": "USR-001",
            "created_by": "USR-001",
            "ideal_cycle_time": Decimal("0.25")
        }

    @staticmethod
    def zero_production_entry():
        """Production entry with zero units (downtime scenario)"""
        return {
            "production_entry_id": "PROD-TEST-ZERO-001",
            "work_order_id": "WO-2025-004",
            "client_id": "BOOT-LINE-A",
            "shift_date": date(2025, 12, 15),
            "shift_type": "SHIFT_1ST",
            "units_produced": 0,  # Downtime day
            "run_time_hours": Decimal("8.0"),
            "employees_assigned": 10,
            "data_collector_id": "USR-001",
            "created_by": "USR-001"
        }

    @staticmethod
    def expected_kpi_results():
        """Expected KPI calculation results for test scenarios"""
        return {
            "TEST_1_PERFECT_DATA": {
                "efficiency": {
                    "hours_produced": Decimal("25.0"),  # 100 × 0.25
                    "hours_available": Decimal("90.0"),  # 10 × 9
                    "efficiency_percent": Decimal("27.78"),
                    "estimated": False,
                    "confidence_score": 1.0
                },
                "performance": {
                    "ideal_hours": Decimal("25.0"),
                    "run_time_hours": Decimal("8.5"),
                    "performance_percent": Decimal("294.12"),  # 25/8.5 * 100
                    "estimated": False
                }
            },
            "TEST_2_MISSING_CYCLE_TIME": {
                "efficiency": {
                    "hours_produced": Decimal("28.0"),  # 100 × 0.28 (inferred)
                    "hours_available": Decimal("90.0"),
                    "efficiency_percent": Decimal("31.11"),
                    "estimated": True,
                    "inference_method": "client_style_average",
                    "confidence_score": 0.85
                }
            },
            "TEST_3_ZERO_PRODUCTION": {
                "efficiency": {
                    "hours_produced": Decimal("0.0"),
                    "efficiency_percent": Decimal("0.0"),
                    "flag_for_review": True
                },
                "performance": {
                    "performance_percent": Decimal("0.0")
                }
            }
        }

    @staticmethod
    def csv_valid_247_rows():
        """Generate CSV with 247 valid rows"""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'work_order_id', 'shift_date', 'shift_type',
            'units_produced', 'run_time_hours', 'employees_assigned', 'notes'
        ])

        writer.writeheader()

        for i in range(247):
            writer.writerow({
                'work_order_id': f'WO-2025-{i:04d}',
                'shift_date': '2025-12-15',
                'shift_type': 'SHIFT_1ST',
                'units_produced': 100 + (i % 50),
                'run_time_hours': 8.5,
                'employees_assigned': 10,
                'notes': f'Test entry {i+1}'
            })

        return output.getvalue()

    @staticmethod
    def csv_with_errors_235_valid_12_invalid():
        """Generate CSV with 247 rows (235 valid, 12 errors)"""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'work_order_id', 'shift_date', 'shift_type',
            'units_produced', 'run_time_hours', 'employees_assigned'
        ])

        writer.writeheader()

        error_rows = [45, 89, 156, 203, 220, 225, 230, 235, 238, 240, 243, 246]

        for i in range(247):
            if i in error_rows:
                # Inject errors
                if i == 45:
                    # Invalid date format
                    writer.writerow({
                        'work_order_id': f'WO-2025-{i:04d}',
                        'shift_date': '12/15/2025',  # Wrong format
                        'shift_type': 'SHIFT_1ST',
                        'units_produced': 100,
                        'run_time_hours': 8.5,
                        'employees_assigned': 10
                    })
                elif i == 89:
                    # Negative units
                    writer.writerow({
                        'work_order_id': f'WO-2025-{i:04d}',
                        'shift_date': '2025-12-15',
                        'shift_type': 'SHIFT_1ST',
                        'units_produced': -5,  # INVALID
                        'run_time_hours': 8.5,
                        'employees_assigned': 10
                    })
                elif i == 156:
                    # Unknown work order
                    writer.writerow({
                        'work_order_id': 'WO-UNKNOWN-XXXX',  # Does not exist
                        'shift_date': '2025-12-15',
                        'shift_type': 'SHIFT_1ST',
                        'units_produced': 100,
                        'run_time_hours': 8.5,
                        'employees_assigned': 10
                    })
                elif i == 203:
                    # Invalid shift type
                    writer.writerow({
                        'work_order_id': f'WO-2025-{i:04d}',
                        'shift_date': '2025-12-15',
                        'shift_type': 'INVALID_SHIFT',  # Not in ENUM
                        'units_produced': 100,
                        'run_time_hours': 8.5,
                        'employees_assigned': 10
                    })
                else:
                    # Other errors (missing fields, etc.)
                    writer.writerow({
                        'work_order_id': f'WO-2025-{i:04d}',
                        'shift_date': '2025-12-15',
                        'shift_type': 'SHIFT_1ST',
                        'units_produced': '',  # Missing
                        'run_time_hours': 8.5,
                        'employees_assigned': 10
                    })
            else:
                # Valid row
                writer.writerow({
                    'work_order_id': f'WO-2025-{i:04d}',
                    'shift_date': '2025-12-15',
                    'shift_type': 'SHIFT_1ST',
                    'units_produced': 100,
                    'run_time_hours': 8.5,
                    'employees_assigned': 10
                })

        return output.getvalue()

    @staticmethod
    def sample_clients():
        """Sample client data for multi-tenant testing"""
        return [
            {
                "client_id": "BOOT-LINE-A",
                "client_name": "Western Boot Line A",
                "location": "Building A",
                "timezone": "America/Mexico_City",
                "is_active": True
            },
            {
                "client_id": "BOOT-LINE-B",
                "client_name": "Western Boot Line B",
                "location": "Building B",
                "timezone": "America/Mexico_City",
                "is_active": True
            },
            {
                "client_id": "CLIENT-C",
                "client_name": "Test Client C",
                "location": "Building C",
                "timezone": "America/Chicago",
                "is_active": True
            }
        ]

    @staticmethod
    def sample_work_orders():
        """Sample work orders for testing"""
        return [
            {
                "work_order_id": "WO-2025-001",
                "client_id": "BOOT-LINE-A",
                "style_model": "ROPER-BOOT",
                "planned_quantity": 1000,
                "planned_start_date": date(2025, 12, 15),
                "planned_ship_date": date(2025, 12, 20),
                "ideal_cycle_time": Decimal("0.25"),
                "status": "ACTIVE"
            },
            {
                "work_order_id": "WO-2025-002",
                "client_id": "BOOT-LINE-A",
                "style_model": "COWBOY-BOOT",
                "planned_quantity": 800,
                "planned_start_date": date(2025, 12, 16),
                "planned_ship_date": date(2025, 12, 22),
                "ideal_cycle_time": None,  # MISSING - test inference
                "status": "ACTIVE"
            }
        ]

    @staticmethod
    def sample_users():
        """Sample users for authentication testing"""
        return [
            {
                "user_id": "USR-001",
                "username": "operator1",
                "full_name": "John Operator",
                "email": "operator1@example.com",
                "role": "OPERATOR_DATAENTRY",
                "client_id_assigned": "BOOT-LINE-A",
                "is_active": True
            },
            {
                "user_id": "USR-002",
                "username": "leader1",
                "full_name": "Jane Leader",
                "email": "leader1@example.com",
                "role": "LEADER_DATACONFIG",
                "client_id_assigned": "BOOT-LINE-A",
                "is_active": True
            },
            {
                "user_id": "USR-003",
                "username": "poweruser1",
                "full_name": "Bob PowerUser",
                "email": "poweruser1@example.com",
                "role": "POWERUSER",
                "client_id_assigned": None,  # Can view all
                "is_active": True
            },
            {
                "user_id": "USR-004",
                "username": "admin1",
                "full_name": "Alice Admin",
                "email": "admin1@example.com",
                "role": "ADMIN",
                "client_id_assigned": None,
                "is_active": True
            }
        ]

    @staticmethod
    def sample_downtime_entries():
        """Sample downtime entries for availability KPI testing"""
        return [
            {
                "downtime_entry_id": "DT-001",
                "work_order_id": "WO-2025-001",
                "client_id": "BOOT-LINE-A",
                "shift_date": date(2025, 12, 15),
                "shift_type": "SHIFT_1ST",
                "downtime_reason": "EQUIPMENT_FAILURE",
                "downtime_duration_minutes": 30,
                "reported_by_user_id": "USR-001"
            },
            {
                "downtime_entry_id": "DT-002",
                "work_order_id": "WO-2025-001",
                "client_id": "BOOT-LINE-A",
                "shift_date": date(2025, 12, 15),
                "shift_type": "SHIFT_2ND",
                "downtime_reason": "MATERIAL_SHORTAGE",
                "downtime_duration_minutes": 120,
                "reported_by_user_id": "USR-001"
            }
        ]

    @staticmethod
    def batch_production_entries(count=100, client_id="BOOT-LINE-A"):
        """Generate batch of production entries for performance testing"""
        entries = []
        start_date = date(2025, 12, 1)

        for i in range(count):
            entries.append({
                "production_entry_id": f"PROD-BATCH-{i:05d}",
                "work_order_id": f"WO-2025-{(i % 10):03d}",
                "client_id": client_id,
                "shift_date": start_date + timedelta(days=i % 30),
                "shift_type": ["SHIFT_1ST", "SHIFT_2ND"][i % 2],
                "units_produced": 100 + (i % 50),
                "units_defective": i % 5,
                "run_time_hours": Decimal("8.5") if i % 2 == 0 else Decimal("7.5"),
                "employees_assigned": 10 if i % 2 == 0 else 8,
                "data_collector_id": "USR-001",
                "entry_method": "CSV_UPLOAD",
                "created_by": "USR-001"
            })

        return entries


class ExpectedTestScenarios:
    """Expected outcomes for specific test scenarios"""

    @staticmethod
    def csv_247_rows_scenario():
        """
        TEST SCENARIO: CSV Upload with 247 Rows

        EXPECTED:
        - Total rows: 247
        - Valid rows: 235
        - Error rows: 12
        - Errors:
          * Row 45: Invalid date format
          * Row 89: Negative units produced
          * Row 156: Unknown work order
          * Row 203: Invalid shift type
          * (8 more miscellaneous errors)
        """
        return {
            "total_rows": 247,
            "valid_rows": 235,
            "error_rows": 12,
            "errors": [
                {"row": 45, "error": "Invalid date format (use YYYY-MM-DD)"},
                {"row": 89, "error": "Negative units produced (-5)"},
                {"row": 156, "error": "Unknown work order WO-UNKNOWN-XXXX"},
                {"row": 203, "error": "Invalid shift_type INVALID_SHIFT"},
                {"row": 220, "error": "Missing required field: units_produced"},
                {"row": 225, "error": "Missing required field: units_produced"},
                {"row": 230, "error": "Missing required field: units_produced"},
                {"row": 235, "error": "Missing required field: units_produced"},
                {"row": 238, "error": "Missing required field: units_produced"},
                {"row": 240, "error": "Missing required field: units_produced"},
                {"row": 243, "error": "Missing required field: units_produced"},
                {"row": 246, "error": "Missing required field: units_produced"}
            ],
            "allow_partial_import": True
        }

    @staticmethod
    def multi_client_isolation_scenario():
        """
        TEST SCENARIO: Multi-Client Data Isolation

        EXPECTED:
        - CLIENT-A sees only their 100 entries
        - CLIENT-B sees only their 150 entries
        - No cross-contamination
        - Concurrent access works correctly
        """
        return {
            "CLIENT-A": {
                "total_entries": 100,
                "total_units": 10000,
                "efficiency": Decimal("27.78")
            },
            "CLIENT-B": {
                "total_entries": 150,
                "total_units": 15000,
                "efficiency": Decimal("32.45")
            }
        }


if __name__ == "__main__":
    # Generate sample files for manual testing
    fixtures = TestDataFixtures()

    # Save valid CSV
    with open("/tmp/test_valid_247.csv", "w") as f:
        f.write(fixtures.csv_valid_247_rows())

    # Save CSV with errors
    with open("/tmp/test_errors_247.csv", "w") as f:
        f.write(fixtures.csv_with_errors_235_valid_12_invalid())

    print("Test fixtures generated:")
    print("- /tmp/test_valid_247.csv")
    print("- /tmp/test_errors_247.csv")
