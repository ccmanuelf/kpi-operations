"""
Unit Tests for Production Models
Tests ProductionEntry Pydantic models and validation
"""

import pytest
from pydantic import ValidationError
from datetime import date, datetime
from decimal import Decimal


@pytest.mark.unit
class TestProductionEntryCreate:
    """Test ProductionEntryCreate model"""

    def test_production_entry_create_valid_data(self):
        """Test creating production entry with valid data"""
        from backend.models.production import ProductionEntryCreate

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            work_order_number="WO-12345",
            units_produced=100,
            run_time_hours=Decimal("8.5"),
            employees_assigned=5,
            defect_count=2,
            scrap_count=1,
            notes="Test production run"
        )

        assert entry.product_id == 1
        assert entry.units_produced == 100
        assert entry.run_time_hours == Decimal("8.5")

    def test_production_entry_create_minimal_data(self):
        """Test creating entry with minimal required fields"""
        from backend.models.production import ProductionEntryCreate

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5
        )

        assert entry.defect_count == 0  # Default
        assert entry.scrap_count == 0  # Default
        assert entry.work_order_number is None
        assert entry.notes is None

    def test_production_entry_invalid_product_id(self):
        """Test validation fails with invalid product_id"""
        from backend.models.production import ProductionEntryCreate

        with pytest.raises(ValidationError):
            ProductionEntryCreate(
                product_id=0,  # Must be > 0
                shift_id=1,
                production_date=date.today(),
                units_produced=100,
                run_time_hours=Decimal("8.0"),
                employees_assigned=5
            )

    def test_production_entry_invalid_units_produced(self):
        """Test validation fails with zero or negative units"""
        from backend.models.production import ProductionEntryCreate

        with pytest.raises(ValidationError):
            ProductionEntryCreate(
                product_id=1,
                shift_id=1,
                production_date=date.today(),
                units_produced=0,  # Must be > 0
                run_time_hours=Decimal("8.0"),
                employees_assigned=5
            )

    def test_production_entry_run_time_exceeds_24_hours(self):
        """Test validation fails when run_time > 24 hours"""
        from backend.models.production import ProductionEntryCreate

        with pytest.raises(ValidationError):
            ProductionEntryCreate(
                product_id=1,
                shift_id=1,
                production_date=date.today(),
                units_produced=100,
                run_time_hours=Decimal("25.0"),  # > 24
                employees_assigned=5
            )

    def test_production_entry_negative_defect_count(self):
        """Test validation fails with negative defects"""
        from backend.models.production import ProductionEntryCreate

        with pytest.raises(ValidationError):
            ProductionEntryCreate(
                product_id=1,
                shift_id=1,
                production_date=date.today(),
                units_produced=100,
                run_time_hours=Decimal("8.0"),
                employees_assigned=5,
                defect_count=-1  # Must be >= 0
            )

    def test_production_entry_too_many_employees(self):
        """Test validation fails with unreasonable employee count"""
        from backend.models.production import ProductionEntryCreate

        with pytest.raises(ValidationError):
            ProductionEntryCreate(
                product_id=1,
                shift_id=1,
                production_date=date.today(),
                units_produced=100,
                run_time_hours=Decimal("8.0"),
                employees_assigned=101  # > 100
            )


@pytest.mark.unit
class TestProductionEntryUpdate:
    """Test ProductionEntryUpdate model"""

    def test_production_entry_update_partial_data(self):
        """Test updating with partial data"""
        from backend.models.production import ProductionEntryUpdate

        update = ProductionEntryUpdate(
            units_produced=150,
            defect_count=3
        )

        assert update.units_produced == 150
        assert update.defect_count == 3
        assert update.run_time_hours is None  # Not updated

    def test_production_entry_update_all_fields(self):
        """Test updating all fields"""
        from backend.models.production import ProductionEntryUpdate

        update = ProductionEntryUpdate(
            units_produced=150,
            run_time_hours=Decimal("9.0"),
            employees_assigned=6,
            defect_count=3,
            scrap_count=2,
            notes="Updated notes",
            confirmed_by=2
        )

        assert update.units_produced == 150
        assert update.confirmed_by == 2


@pytest.mark.unit
class TestProductionEntryResponse:
    """Test ProductionEntryResponse model"""

    def test_production_entry_response_all_fields(self):
        """Test response model with all fields"""
        from backend.models.production import ProductionEntryResponse

        entry = ProductionEntryResponse(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            work_order_number="WO-12345",
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=2,
            scrap_count=1,
            efficiency_percentage=Decimal("85.5"),
            performance_percentage=Decimal("92.3"),
            notes="Test notes",
            entered_by=1,
            confirmed_by=None,
            confirmation_timestamp=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        assert entry.entry_id == 1
        assert entry.efficiency_percentage == Decimal("85.5")

    def test_production_entry_response_optional_kpis(self):
        """Test response model with optional KPIs as None"""
        from backend.models.production import ProductionEntryResponse

        entry = ProductionEntryResponse(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            work_order_number=None,
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            efficiency_percentage=None,  # Not calculated yet
            performance_percentage=None,  # Not calculated yet
            notes=None,
            entered_by=1,
            confirmed_by=None,
            confirmation_timestamp=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        assert entry.efficiency_percentage is None
        assert entry.performance_percentage is None


@pytest.mark.unit
class TestProductionEntryWithKPIs:
    """Test ProductionEntryWithKPIs model"""

    def test_entry_with_kpis_extended_fields(self):
        """Test extended model includes additional KPI fields"""
        from backend.models.production import ProductionEntryWithKPIs

        entry = ProductionEntryWithKPIs(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            work_order_number="WO-12345",
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=2,
            scrap_count=1,
            efficiency_percentage=Decimal("85.5"),
            performance_percentage=Decimal("92.3"),
            notes="Test notes",
            entered_by=1,
            confirmed_by=None,
            confirmation_timestamp=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            # Extended fields
            product_name="Product A",
            shift_name="Day Shift",
            ideal_cycle_time=Decimal("0.25"),
            inferred_cycle_time=False,
            total_available_hours=Decimal("40.0"),
            quality_rate=Decimal("97.0"),
            oee=Decimal("75.8")
        )

        assert entry.product_name == "Product A"
        assert entry.shift_name == "Day Shift"
        assert entry.ideal_cycle_time == Decimal("0.25")
        assert entry.oee == Decimal("75.8")


@pytest.mark.unit
class TestKPICalculationResponse:
    """Test KPICalculationResponse model"""

    def test_kpi_calculation_response(self):
        """Test KPI calculation response structure"""
        from backend.models.production import KPICalculationResponse

        response = KPICalculationResponse(
            entry_id=1,
            efficiency_percentage=Decimal("85.5"),
            performance_percentage=Decimal("92.3"),
            quality_rate=Decimal("97.0"),
            ideal_cycle_time_used=Decimal("0.25"),
            was_inferred=False,
            calculation_timestamp=datetime.utcnow()
        )

        assert response.entry_id == 1
        assert response.efficiency_percentage == Decimal("85.5")
        assert response.was_inferred == False

    def test_kpi_calculation_with_inferred_cycle_time(self):
        """Test KPI calculation when cycle time was inferred"""
        from backend.models.production import KPICalculationResponse

        response = KPICalculationResponse(
            entry_id=1,
            efficiency_percentage=Decimal("88.2"),
            performance_percentage=Decimal("95.1"),
            quality_rate=Decimal("98.5"),
            ideal_cycle_time_used=Decimal("0.28"),
            was_inferred=True,  # Inferred from historical data
            calculation_timestamp=datetime.utcnow()
        )

        assert response.was_inferred == True
        assert response.ideal_cycle_time_used == Decimal("0.28")


@pytest.mark.unit
class TestCSVUploadResponse:
    """Test CSVUploadResponse model"""

    def test_csv_upload_response_success(self):
        """Test CSV upload response for successful upload"""
        from backend.models.production import CSVUploadResponse

        response = CSVUploadResponse(
            total_rows=247,
            successful=247,
            failed=0,
            errors=[],
            created_entries=[1, 2, 3, 4, 5]
        )

        assert response.total_rows == 247
        assert response.successful == 247
        assert response.failed == 0
        assert len(response.errors) == 0

    def test_csv_upload_response_with_errors(self):
        """Test CSV upload response with errors"""
        from backend.models.production import CSVUploadResponse

        response = CSVUploadResponse(
            total_rows=247,
            successful=235,
            failed=12,
            errors=[
                {"row": 5, "error": "Invalid product_id", "data": {}},
                {"row": 12, "error": "Missing required field", "data": {}}
            ],
            created_entries=list(range(1, 236))
        )

        assert response.total_rows == 247
        assert response.successful == 235
        assert response.failed == 12
        assert len(response.errors) == 2


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases for production models"""

    def test_maximum_units_produced(self):
        """Test very large units_produced value"""
        from backend.models.production import ProductionEntryCreate

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=1000000,  # 1 million units
            run_time_hours=Decimal("24.0"),
            employees_assigned=100
        )

        assert entry.units_produced == 1000000

    def test_minimum_run_time(self):
        """Test minimum run time (near zero)"""
        from backend.models.production import ProductionEntryCreate

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=1,
            run_time_hours=Decimal("0.1"),  # 6 minutes
            employees_assigned=1
        )

        assert entry.run_time_hours == Decimal("0.1")

    def test_defects_exceed_production(self):
        """Test when defects + scrap > units_produced"""
        from backend.models.production import ProductionEntryCreate

        # This should be allowed at model level, business logic validates later
        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=60,
            scrap_count=50  # Total 110 > 100
        )

        assert entry.defect_count == 60
        assert entry.scrap_count == 50

    def test_future_production_date(self):
        """Test production date in the future"""
        from backend.models.production import ProductionEntryCreate
        from datetime import timedelta

        future_date = date.today() + timedelta(days=7)

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=future_date,
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5
        )

        assert entry.production_date == future_date

    def test_work_order_number_max_length(self):
        """Test work order number length limit"""
        from backend.models.production import ProductionEntryCreate

        long_wo = "WO-" + "X" * 47  # 50 characters

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            work_order_number=long_wo,
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5
        )

        assert entry.work_order_number == long_wo


@pytest.mark.unit
class TestDecimalPrecision:
    """Test decimal precision handling"""

    def test_run_time_precision(self):
        """Test run_time_hours decimal precision"""
        from backend.models.production import ProductionEntryCreate

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.333333"),
            employees_assigned=5
        )

        assert isinstance(entry.run_time_hours, Decimal)

    def test_kpi_percentage_precision(self):
        """Test KPI percentage precision"""
        from backend.models.production import KPICalculationResponse

        response = KPICalculationResponse(
            entry_id=1,
            efficiency_percentage=Decimal("85.555"),
            performance_percentage=Decimal("92.333"),
            quality_rate=Decimal("97.777"),
            ideal_cycle_time_used=Decimal("0.25"),
            was_inferred=False,
            calculation_timestamp=datetime.utcnow()
        )

        assert isinstance(response.efficiency_percentage, Decimal)
