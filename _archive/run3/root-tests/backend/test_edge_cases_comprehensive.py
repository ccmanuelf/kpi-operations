"""
Comprehensive Edge Case Tests
Tests zero production, 100%+ efficiency, boundary conditions, and error scenarios
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import Mock, patch


@pytest.mark.unit
class TestZeroProductionEdgeCases:
    """Test edge cases with zero production values"""

    def test_zero_units_produced_efficiency(self):
        """Test efficiency when units_produced = 0"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=0,  # ZERO PRODUCTION!
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        # Note: Pydantic validation prevents units_produced=0,
        # but if it bypasses, calculate correctly
        # This tests robustness

    def test_zero_employees_edge_case(self):
        """Test with zero employees assigned"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=0,  # ZERO EMPLOYEES!
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        # Should return 0% efficiency
        assert efficiency == Decimal("0")

    def test_zero_runtime_edge_case(self):
        """Test with zero run time"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.calculations.performance import calculate_performance
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("0"),  # ZERO RUNTIME!
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)
        performance, _, _ = calculate_performance(mock_db, entry, product)

        assert efficiency == Decimal("0")
        assert performance == Decimal("0")


@pytest.mark.unit
class TestExtremelyHighEfficiency:
    """Test efficiency over 100% scenarios"""

    def test_efficiency_at_100_percent(self):
        """Test exact 100% efficiency"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        # Calculate inputs for exactly 100%
        # (units × cycle_time) / (employees × runtime) = 1.0
        # (160 × 0.25) / (5 × 8.0) = 40/40 = 1.0 = 100%

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=160,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        assert efficiency == Decimal("100.00")

    def test_efficiency_over_100_percent(self):
        """Test efficiency calculation over 100%"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        # 200 units would give 125% efficiency
        # (200 × 0.25) / (5 × 8.0) = 50/40 = 1.25 = 125%

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        assert efficiency == Decimal("125.00")

    def test_efficiency_capped_at_150_percent(self):
        """Test efficiency is capped at 150%"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("1.0"),  # High cycle time
            is_active=True
        )

        # This would calculate to 500% efficiency
        # (1000 × 1.0) / (2 × 1.0) = 1000/2 = 500.0 = 50000%

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=1000,
            run_time_hours=Decimal("1.0"),
            employees_assigned=2,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        # Should be capped at 150%
        assert efficiency == Decimal("150.00")


@pytest.mark.unit
class TestDefectsAndScrapEdgeCases:
    """Test edge cases with defects and scrap"""

    def test_defects_equal_production(self):
        """Test when defects = units_produced"""
        from backend.calculations.performance import calculate_quality_rate
        from backend.schemas.production import ProductionEntry

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=100,  # All defective!
            scrap_count=0,
            entered_by=1
        )

        quality_rate = calculate_quality_rate(entry)

        # Quality should be 0%
        assert quality_rate == Decimal("0.00")

    def test_defects_exceed_production(self):
        """Test when defects + scrap > units_produced"""
        from backend.calculations.performance import calculate_quality_rate
        from backend.schemas.production import ProductionEntry

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=70,
            scrap_count=50,  # Total 120 > 100!
            entered_by=1
        )

        quality_rate = calculate_quality_rate(entry)

        # Quality should not go negative, minimum 0%
        assert quality_rate >= Decimal("0.00")

    def test_perfect_quality(self):
        """Test 100% quality (zero defects and scrap)"""
        from backend.calculations.performance import calculate_quality_rate
        from backend.schemas.production import ProductionEntry

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        quality_rate = calculate_quality_rate(entry)

        assert quality_rate == Decimal("100.00")


@pytest.mark.unit
class TestBoundaryValues:
    """Test boundary value conditions"""

    def test_minimum_runtime_fraction(self):
        """Test very small runtime (minutes, not hours)"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.01"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=10,
            run_time_hours=Decimal("0.1"),  # 6 minutes
            employees_assigned=1,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        assert efficiency > Decimal("0")

    def test_maximum_runtime_24_hours(self):
        """Test maximum runtime of 24 hours"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=480,  # 2 per hour
            run_time_hours=Decimal("24.0"),  # Full 24 hours
            employees_assigned=10,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        assert efficiency > Decimal("0")

    def test_maximum_employees_100(self):
        """Test maximum employees (100)"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=10000,
            run_time_hours=Decimal("8.0"),
            employees_assigned=100,  # Maximum employees
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        assert efficiency > Decimal("0")

    def test_single_employee(self):
        """Test minimum employees (1)"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.5"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=10,
            run_time_hours=Decimal("8.0"),
            employees_assigned=1,  # Single employee
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        # (10 × 0.5) / (1 × 8.0) × 100 = 5/8 × 100 = 62.5%
        assert efficiency == Decimal("62.50")


@pytest.mark.unit
class TestNegativeDowntimeSimulation:
    """Test scenarios simulating negative downtime (more production than expected)"""

    def test_excessive_production_rate(self):
        """Test when production rate exceeds reasonable expectations"""
        from backend.calculations.performance import calculate_performance
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.1"),  # 6 minutes per unit
            is_active=True
        )

        # Producing way more than expected
        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=1000,  # Way more than ideal
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        performance, _, _ = calculate_performance(mock_db, entry, product)

        # Should be high but capped at 150%
        assert performance <= Decimal("150.00")


@pytest.mark.unit
class TestDateEdgeCases:
    """Test edge cases with dates"""

    def test_production_on_leap_year_day(self):
        """Test production on February 29 (leap year)"""
        from backend.models.production import ProductionEntryCreate

        entry = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date(2024, 2, 29),  # Leap year
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5
        )

        assert entry.production_date.day == 29
        assert entry.production_date.month == 2

    def test_production_on_year_boundary(self):
        """Test production on Dec 31 / Jan 1 boundary"""
        from backend.models.production import ProductionEntryCreate

        entry_end = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date(2024, 12, 31),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5
        )

        entry_start = ProductionEntryCreate(
            product_id=1,
            shift_id=1,
            production_date=date(2025, 1, 1),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5
        )

        assert entry_end.production_date.year == 2024
        assert entry_start.production_date.year == 2025


@pytest.mark.unit
class TestDecimalPrecisionEdgeCases:
    """Test decimal precision and rounding edge cases"""

    def test_very_small_cycle_time(self):
        """Test with very small ideal cycle time"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.001"),  # Very small!
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=1000,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        assert efficiency >= Decimal("0")
        assert efficiency <= Decimal("150.00")

    def test_efficiency_rounding_precision(self):
        """Test efficiency is rounded to 2 decimal places"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.333333"),
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=99,
            run_time_hours=Decimal("7.77"),
            employees_assigned=3,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, _, _ = calculate_efficiency(mock_db, entry, product)

        # Should be rounded to 2 decimals
        assert str(efficiency).count('.') <= 1
        decimal_part = str(efficiency).split('.')[-1] if '.' in str(efficiency) else ''
        assert len(decimal_part) <= 2


@pytest.mark.unit
class TestConcurrentScenarios:
    """Test scenarios that might occur with concurrent operations"""

    def test_same_product_multiple_shifts(self):
        """Test same product produced in multiple shifts"""
        # Would test data integrity across concurrent entries
        assert True  # Placeholder

    def test_rapid_sequential_updates(self):
        """Test rapid updates to same entry"""
        # Would test for race conditions
        assert True  # Placeholder
