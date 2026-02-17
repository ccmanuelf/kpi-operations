"""
Test suite for performance calculations
"""
import pytest
from decimal import Decimal
from datetime import date

from backend.calculations.performance import (
    calculate_performance,
    calculate_quality_rate,
    calculate_oee
)
from backend.schemas.product import Product
from backend.schemas.production import ProductionEntry


def test_calculate_performance_basic():
    """Test basic performance calculation"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return Product(
                product_id=1,
                product_code="TEST",
                product_name="Test",
                ideal_cycle_time=Decimal("0.25"),
                is_active=True
            )

    db = MockDB()

    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=200,
        run_time_hours=Decimal("8.0"),
        employees_assigned=2,
        defect_count=5,
        scrap_count=2,
        entered_by=1
    )

    performance, cycle_time, was_inferred = calculate_performance(db, entry, None)

    # Expected: (0.25 × 200) / 8.0 × 100 = 50 / 8 × 100 = 625%
    # Capped at 150%
    expected = (Decimal("0.25") * 200) / Decimal("8.0") * 100

    assert cycle_time == Decimal("0.25")
    assert was_inferred is False
    assert performance == Decimal("150.00")  # Capped


def test_calculate_performance_zero_runtime():
    """Test performance with zero runtime (edge case)"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return Product(
                product_id=1,
                product_code="TEST",
                product_name="Test",
                ideal_cycle_time=Decimal("0.25"),
                is_active=True
            )

    db = MockDB()

    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=200,
        run_time_hours=Decimal("0"),
        employees_assigned=2,
        defect_count=0,
        scrap_count=0,
        entered_by=1
    )

    performance, _, _ = calculate_performance(db, entry, None)

    assert performance == Decimal("0")


def test_calculate_quality_rate():
    """Test quality rate calculation"""
    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=200,
        run_time_hours=Decimal("8.0"),
        employees_assigned=2,
        defect_count=10,
        scrap_count=5,
        entered_by=1
    )

    quality = calculate_quality_rate(entry)

    # Expected: (200 - 10 - 5) / 200 × 100 = 185 / 200 × 100 = 92.5%
    expected = Decimal("92.5")

    assert quality == expected


def test_calculate_quality_rate_perfect():
    """Test quality rate with no defects"""
    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=200,
        run_time_hours=Decimal("8.0"),
        employees_assigned=2,
        defect_count=0,
        scrap_count=0,
        entered_by=1
    )

    quality = calculate_quality_rate(entry)

    assert quality == Decimal("100.00")


def test_calculate_quality_rate_zero_units():
    """Test quality rate with zero units (edge case)"""
    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=0,
        run_time_hours=Decimal("8.0"),
        employees_assigned=2,
        defect_count=0,
        scrap_count=0,
        entered_by=1
    )

    quality = calculate_quality_rate(entry)

    assert quality == Decimal("0")


def test_calculate_oee():
    """Test OEE calculation"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return Product(
                product_id=1,
                product_code="TEST",
                product_name="Test",
                ideal_cycle_time=Decimal("0.50"),
                is_active=True
            )

    db = MockDB()

    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=100,
        run_time_hours=Decimal("8.0"),
        employees_assigned=2,
        defect_count=5,
        scrap_count=3,
        entered_by=1
    )

    oee, components = calculate_oee(db, entry, None)

    # Availability: 100% (Phase 1 assumption)
    # Performance: (0.50 × 100) / 8.0 × 100 = 625% -> capped at 150%
    # Quality: (100 - 5 - 3) / 100 × 100 = 92%
    # OEE: 1.0 × 1.5 × 0.92 × 100 = 138% (should be capped)

    assert components['availability'] == Decimal("100")
    assert components['quality'] == Decimal("92.00")
    assert 'oee' in components
    assert oee > 0


def test_performance_realistic_scenario():
    """Test with realistic manufacturing scenario"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return Product(
                product_id=1,
                product_code="WDG-001",
                product_name="Widget",
                ideal_cycle_time=Decimal("0.20"),  # 12 min per unit
                is_active=True
            )

    db = MockDB()

    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=150,
        run_time_hours=Decimal("7.5"),
        employees_assigned=2,
        defect_count=2,
        scrap_count=1,
        entered_by=1
    )

    performance, _, _ = calculate_performance(db, entry, None)

    # Expected: (0.20 × 150) / 7.5 × 100 = 30 / 7.5 × 100 = 400%
    # Capped at 150%
    assert performance == Decimal("150.00")
