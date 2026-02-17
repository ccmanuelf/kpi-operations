"""
End-to-End Production Workflow Tests
Tests complete workflows: CSV Upload → Data Preview → Import → KPI Calculation → Verification
"""
import pytest
import io
import csv
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.product import Product
from backend.schemas.shift import Shift


@pytest.fixture
def test_user(test_db: Session):
    """Create test user"""
    user = User(
        username="e2e_user",
        email="e2e@test.com",
        password_hash="hashed",
        role="SUPERVISOR",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def test_product(test_db: Session):
    """Create test product"""
    product = Product(
        product_code="E2E-PROD-001",
        product_name="E2E Test Product",
        ideal_cycle_time=Decimal("0.25"),
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def test_shift(test_db: Session):
    """Create test shift"""
    shift = Shift(
        shift_name="E2E Day Shift",
        start_time="08:00",
        end_time="16:00",
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


class TestCSVUploadWorkflow:
    """Test CSV upload → preview → import → verify workflow"""

    def test_csv_upload_complete_workflow(self, test_db, test_user, test_product, test_shift):
        """Should upload CSV, preview data, import, and verify KPIs"""
        from backend.crud.production import create_production_entry, get_production_entries
        from backend.models.production import ProductionEntryCreate
        from backend.calculations.efficiency import calculate_efficiency
        from backend.calculations.performance import calculate_performance

        # Step 1: Create CSV data
        csv_data = io.StringIO()
        csv_writer = csv.DictWriter(csv_data, fieldnames=[
            'product_id', 'shift_id', 'production_date', 'work_order_number',
            'units_produced', 'run_time_hours', 'employees_assigned',
            'defect_count', 'scrap_count', 'notes'
        ])
        csv_writer.writeheader()
        csv_writer.writerow({
            'product_id': test_product.product_id,
            'shift_id': test_shift.shift_id,
            'production_date': '2025-12-31',
            'work_order_number': 'WO-E2E-001',
            'units_produced': '250',
            'run_time_hours': '7.5',
            'employees_assigned': '3',
            'defect_count': '5',
            'scrap_count': '2',
            'notes': 'E2E test entry'
        })

        # Step 2: Parse and preview CSV
        csv_data.seek(0)
        csv_reader = csv.DictReader(csv_data)
        preview_rows = list(csv_reader)

        assert len(preview_rows) == 1
        assert preview_rows[0]['units_produced'] == '250'

        # Step 3: Import data
        imported_entries = []
        for row in preview_rows:
            entry_data = ProductionEntryCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                production_date=date(2025, 12, 31),
                work_order_number=row['work_order_number'],
                units_produced=int(row['units_produced']),
                run_time_hours=Decimal(row['run_time_hours']),
                employees_assigned=int(row['employees_assigned']),
                defect_count=int(row['defect_count']),
                scrap_count=int(row['scrap_count']),
                notes=row.get('notes')
            )

            created = create_production_entry(test_db, entry_data, test_user)
            imported_entries.append(created)

        assert len(imported_entries) == 1

        # Step 4: Verify data persisted
        all_entries = get_production_entries(test_db, test_user)
        assert len(all_entries) == 1

        # Step 5: Calculate and verify KPIs
        entry = imported_entries[0]

        # Calculate efficiency
        efficiency, cycle_time, was_inferred = calculate_efficiency(
            test_db, entry, test_product
        )

        # Expected: (250 units * 0.25 hrs/unit) / (3 employees * 7.5 hrs) * 100
        # = 62.5 / 22.5 * 100 = 277.78% (capped at 150%)
        assert efficiency == Decimal("150.00")
        assert cycle_time == Decimal("0.25")
        assert was_inferred is False

        # Calculate performance
        performance, _, _ = calculate_performance(test_db, entry, test_product)
        assert performance > Decimal("0.0")

    def test_csv_validation_and_error_handling(self, test_db, test_user, test_product, test_shift):
        """Should validate CSV data and handle errors gracefully"""
        from backend.crud.production import create_production_entry
        from backend.models.production import ProductionEntryCreate

        # Create CSV with invalid data
        invalid_rows = [
            # Missing required field
            {
                'product_id': test_product.product_id,
                'shift_id': test_shift.shift_id,
                'production_date': '2025-12-31',
                'units_produced': '250',
                # Missing run_time_hours
                'employees_assigned': '3',
            },
            # Invalid date format
            {
                'product_id': test_product.product_id,
                'shift_id': test_shift.shift_id,
                'production_date': 'invalid-date',
                'units_produced': '250',
                'run_time_hours': '7.5',
                'employees_assigned': '3',
            },
            # Valid row
            {
                'product_id': test_product.product_id,
                'shift_id': test_shift.shift_id,
                'production_date': '2025-12-31',
                'units_produced': '250',
                'run_time_hours': '7.5',
                'employees_assigned': '3',
                'defect_count': '0',
                'scrap_count': '0'
            }
        ]

        successful = 0
        failed = 0
        errors = []

        for row in invalid_rows:
            try:
                entry_data = ProductionEntryCreate(
                    product_id=int(row['product_id']),
                    shift_id=int(row['shift_id']),
                    production_date=date.fromisoformat(row['production_date']),
                    units_produced=int(row['units_produced']),
                    run_time_hours=Decimal(row['run_time_hours']),
                    employees_assigned=int(row['employees_assigned']),
                    defect_count=int(row.get('defect_count', 0)),
                    scrap_count=int(row.get('scrap_count', 0))
                )

                create_production_entry(test_db, entry_data, test_user)
                successful += 1

            except Exception as e:
                failed += 1
                errors.append(str(e))

        # Should have 1 successful, 2 failed
        assert successful == 1
        assert failed == 2
        assert len(errors) == 2


class TestGridEditingWorkflow:
    """Test grid editing → save → verify workflow"""

    def test_inline_edit_and_save(self, test_db, test_user, test_product, test_shift):
        """Should edit production entry inline and save changes"""
        from backend.crud.production import create_production_entry, update_production_entry
        from backend.models.production import ProductionEntryCreate, ProductionEntryUpdate
        from backend.calculations.efficiency import calculate_efficiency

        # Step 1: Create initial entry
        entry_data = ProductionEntryCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            production_date=date.today(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=2,
            defect_count=5,
            scrap_count=1
        )

        created = create_production_entry(test_db, entry_data, test_user)

        # Step 2: Edit units_produced in grid
        update_data = ProductionEntryUpdate(
            units_produced=250,
            defect_count=3
        )

        updated = update_production_entry(
            test_db, created.entry_id, update_data, test_user
        )

        # Step 3: Verify changes
        assert updated.units_produced == 250
        assert updated.defect_count == 3
        assert updated.run_time_hours == Decimal("8.0")  # Unchanged

        # Step 4: Recalculate KPIs with new values
        efficiency_before = calculate_efficiency(test_db, created, test_product)[0]
        efficiency_after = calculate_efficiency(test_db, updated, test_product)[0]

        # Efficiency should increase (more units produced)
        assert efficiency_after > efficiency_before


class TestBulkOperationsWorkflow:
    """Test bulk import and batch processing workflows"""

    def test_bulk_import_100_records(self, test_db, test_user, test_product, test_shift):
        """Should bulk import 100 production records efficiently"""
        from backend.crud.production import create_production_entry
        from backend.models.production import ProductionEntryCreate
        import time

        # Create 100 entries
        start_time = time.time()
        created_entries = []

        for i in range(100):
            entry_data = ProductionEntryCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                production_date=date.today(),
                units_produced=200 + i,
                run_time_hours=Decimal("8.0"),
                employees_assigned=3,
                defect_count=i % 10,
                scrap_count=i % 5
            )

            created = create_production_entry(test_db, entry_data, test_user)
            created_entries.append(created)

        end_time = time.time()
        duration = end_time - start_time

        # Verify all created
        assert len(created_entries) == 100

        # Should complete in reasonable time (< 10 seconds)
        assert duration < 10.0

    def test_batch_kpi_calculation(self, test_db, test_user, test_product, test_shift):
        """Should calculate KPIs for batch of entries"""
        from backend.crud.production import create_production_entry
        from backend.models.production import ProductionEntryCreate
        from backend.calculations.efficiency import calculate_efficiency

        # Create multiple entries
        entries = []
        for i in range(10):
            entry_data = ProductionEntryCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                production_date=date.today(),
                units_produced=200,
                run_time_hours=Decimal("8.0"),
                employees_assigned=2,
                defect_count=5,
                scrap_count=1
            )

            created = create_production_entry(test_db, entry_data, test_user)
            entries.append(created)

        # Calculate KPIs for all
        kpi_results = []
        for entry in entries:
            efficiency, _, _ = calculate_efficiency(test_db, entry, test_product)
            kpi_results.append({
                'entry_id': entry.entry_id,
                'efficiency': efficiency
            })

        # Verify all calculated
        assert len(kpi_results) == 10
        assert all(r['efficiency'] > Decimal("0.0") for r in kpi_results)


class TestKPIDashboardWorkflow:
    """Test KPI dashboard data aggregation workflow"""

    def test_daily_summary_generation(self, test_db, test_user, test_product, test_shift):
        """Should generate daily KPI summary"""
        from backend.crud.production import create_production_entry, get_daily_summary
        from backend.models.production import ProductionEntryCreate

        # Create entries for today
        for i in range(5):
            entry_data = ProductionEntryCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                production_date=date.today(),
                units_produced=200,
                run_time_hours=Decimal("8.0"),
                employees_assigned=2,
                defect_count=5,
                scrap_count=1
            )

            create_production_entry(test_db, entry_data, test_user)

        # Get daily summary
        summary = get_daily_summary(test_db, date.today(), date.today(), test_user)

        # Verify summary data
        assert summary is not None
        assert summary['total_entries'] == 5
        assert summary['total_units'] == 1000  # 5 entries * 200 units
        assert 'average_efficiency' in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
