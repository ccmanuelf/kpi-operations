"""
Test suite for efficiency calculations
"""
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session

from backend.calculations.efficiency import (
    calculate_efficiency,
    infer_ideal_cycle_time,
    DEFAULT_CYCLE_TIME
)
from backend.schemas.product import Product
from backend.schemas.production import ProductionEntry


@pytest.fixture
def sample_product():
    """Sample product with defined cycle time"""
    return Product(
        product_id=1,
        product_code="TEST-001",
        product_name="Test Product",
        ideal_cycle_time=Decimal("0.25"),
        is_active=True
    )


@pytest.fixture
def sample_product_no_cycle():
    """Sample product without cycle time (triggers inference)"""
    return Product(
        product_id=2,
        product_code="TEST-002",
        product_name="Test Product No Cycle",
        ideal_cycle_time=None,
        is_active=True
    )


@pytest.fixture
def sample_entry():
    """Sample production entry"""
    return ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=250,
        run_time_hours=Decimal("7.5"),
        employees_assigned=3,
        defect_count=5,
        scrap_count=2,
        entered_by=1
    )


def test_calculate_efficiency_with_defined_cycle_time(sample_product, sample_entry):
    """Test efficiency calculation with defined ideal cycle time"""
    # Mock db
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return sample_product

    db = MockDB()

    efficiency, cycle_time, was_inferred = calculate_efficiency(db, sample_entry, sample_product)

    # Expected: (250 × 0.25) / (3 × 7.5) × 100 = 62.5 / 22.5 × 100 = 277.78%
    # Capped at 150%
    expected = Decimal("62.5") / Decimal("22.5") * 100

    assert cycle_time == Decimal("0.25")
    assert was_inferred is False
    assert efficiency > 0
    assert efficiency <= 150


def test_calculate_efficiency_zero_employees(sample_product, sample_entry):
    """Test efficiency with zero employees (edge case)"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return sample_product

    db = MockDB()

    sample_entry.employees_assigned = 0

    efficiency, cycle_time, was_inferred = calculate_efficiency(db, sample_entry, sample_product)

    assert efficiency == Decimal("0")


def test_calculate_efficiency_zero_runtime(sample_product, sample_entry):
    """Test efficiency with zero runtime (edge case)"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return sample_product

    db = MockDB()

    sample_entry.run_time_hours = Decimal("0")

    efficiency, cycle_time, was_inferred = calculate_efficiency(db, sample_entry, sample_product)

    assert efficiency == Decimal("0")


def test_infer_ideal_cycle_time_uses_default():
    """Test that inference uses default when no product or history"""
    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

        def limit(self, n):
            return self

        def all(self):
            return []

    db = MockDB()

    cycle_time, was_inferred = infer_ideal_cycle_time(db, 1)

    assert cycle_time == DEFAULT_CYCLE_TIME
    assert was_inferred is False


def test_efficiency_realistic_scenario():
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
                ideal_cycle_time=Decimal("0.25"),  # 15 min per unit
                is_active=True
            )

    db = MockDB()

    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=200,  # 200 units
        run_time_hours=Decimal("8.0"),  # 8 hour shift
        employees_assigned=2,  # 2 workers
        defect_count=3,
        scrap_count=1,
        entered_by=1
    )

    efficiency, _, _ = calculate_efficiency(db, entry, None)

    # Expected: (200 × 0.25) / (2 × 8.0) × 100 = 50 / 16 × 100 = 312.5%
    # Capped at 150%
    assert efficiency == Decimal("150.00")


def test_efficiency_calculation_precision():
    """Test that efficiency is calculated to 2 decimal places"""
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
                ideal_cycle_time=Decimal("0.33"),
                is_active=True
            )

    db = MockDB()

    entry = ProductionEntry(
        entry_id=1,
        product_id=1,
        shift_id=1,
        production_date=date(2025, 12, 31),
        units_produced=100,
        run_time_hours=Decimal("7.5"),
        employees_assigned=3,
        defect_count=0,
        scrap_count=0,
        entered_by=1
    )

    efficiency, _, _ = calculate_efficiency(db, entry, None)

    # Check precision (2 decimal places)
    assert str(efficiency).count('.') == 1
    assert len(str(efficiency).split('.')[1]) <= 2
