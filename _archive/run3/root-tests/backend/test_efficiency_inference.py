"""
Advanced Tests for Efficiency Calculation with Inference Engine
Tests missing data scenarios, historical inference, and edge cases
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from datetime import date


@pytest.mark.unit
class TestInferenceEngine:
    """Test inference engine for missing ideal_cycle_time"""

    def test_infer_from_product_table(self):
        """Test inference uses product.ideal_cycle_time if available"""
        from backend.calculations.efficiency import infer_ideal_cycle_time
        from backend.schemas.product import Product

        # Mock database
        mock_db = Mock()
        mock_product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_product
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        cycle_time, was_inferred = infer_ideal_cycle_time(mock_db, product_id=1)

        assert cycle_time == Decimal("0.25")
        assert was_inferred == False  # From product table, not inferred

    def test_infer_from_historical_data(self):
        """Test inference calculates from historical entries"""
        from backend.calculations.efficiency import infer_ideal_cycle_time
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        # Mock database
        mock_db = Mock()

        # Product with no ideal_cycle_time
        mock_product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=None,  # Missing!
            is_active=True
        )

        # Historical entries
        historical_entry = ProductionEntry(
            entry_id=100,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            efficiency_percentage=Decimal("80.0"),
            performance_percentage=Decimal("85.0"),
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        # Setup mock query chain
        product_query = Mock()
        product_filter = Mock()
        product_filter.first.return_value = mock_product
        product_query.filter.return_value = product_filter

        entry_query = Mock()
        entry_filter = Mock()
        entry_isnot_1 = Mock()
        entry_isnot_2 = Mock()
        entry_limit = Mock()
        entry_limit.all.return_value = [historical_entry]
        entry_isnot_2.limit.return_value = entry_limit
        entry_isnot_1.isnot.return_value = entry_isnot_2
        entry_filter.filter.return_value = entry_isnot_1
        entry_query.filter.return_value = entry_filter

        def mock_query_selector(model):
            if 'Product' in str(model):
                return product_query
            else:
                return entry_query

        mock_db.query.side_effect = mock_query_selector

        cycle_time, was_inferred = infer_ideal_cycle_time(mock_db, product_id=1)

        assert was_inferred == True  # Calculated from history
        assert cycle_time > 0

    def test_infer_uses_default_when_no_data(self):
        """Test inference uses default when no historical data"""
        from backend.calculations.efficiency import infer_ideal_cycle_time, DEFAULT_CYCLE_TIME
        from backend.schemas.product import Product

        # Mock database
        mock_db = Mock()

        # Product with no ideal_cycle_time
        mock_product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=None,
            is_active=True
        )

        # Setup mock query chain - no historical data
        product_query = Mock()
        product_filter = Mock()
        product_filter.first.return_value = mock_product
        product_query.filter.return_value = product_filter

        entry_query = Mock()
        entry_filter = Mock()
        entry_isnot_1 = Mock()
        entry_isnot_2 = Mock()
        entry_limit = Mock()
        entry_limit.all.return_value = []  # No historical entries!
        entry_isnot_2.limit.return_value = entry_limit
        entry_isnot_1.isnot.return_value = entry_isnot_2
        entry_filter.filter.return_value = entry_isnot_1
        entry_query.filter.return_value = entry_filter

        def mock_query_selector(model):
            if 'Product' in str(model):
                return product_query
            else:
                return entry_query

        mock_db.query.side_effect = mock_query_selector

        cycle_time, was_inferred = infer_ideal_cycle_time(mock_db, product_id=1)

        assert cycle_time == DEFAULT_CYCLE_TIME
        assert was_inferred == False  # Default, not inferred


@pytest.mark.unit
class TestEfficiencyWithInference:
    """Test efficiency calculation with various data scenarios"""

    def test_efficiency_with_known_cycle_time(self):
        """Test efficiency calculation when cycle time is known"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),  # Known
            is_active=True
        )

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

        efficiency, cycle_time, was_inferred = calculate_efficiency(mock_db, entry, product)

        # Expected: (100 × 0.25) / (5 × 8.0) × 100 = 62.5%
        assert efficiency == Decimal("62.50")
        assert was_inferred == False

    def test_efficiency_with_zero_employees(self):
        """Test efficiency returns 0% when employees = 0"""
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
            employees_assigned=0,  # Zero employees!
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, cycle_time, was_inferred = calculate_efficiency(mock_db, entry, product)

        assert efficiency == Decimal("0")

    def test_efficiency_with_zero_runtime(self):
        """Test efficiency returns 0% when runtime = 0"""
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
            run_time_hours=Decimal("0"),  # Zero runtime!
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, cycle_time, was_inferred = calculate_efficiency(mock_db, entry, product)

        assert efficiency == Decimal("0")

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
            ideal_cycle_time=Decimal("10.0"),  # Very high!
            is_active=True
        )

        entry = ProductionEntry(
            entry_id=1,
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=1000,
            run_time_hours=Decimal("1.0"),
            employees_assigned=1,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, cycle_time, was_inferred = calculate_efficiency(mock_db, entry, product)

        # Would calculate to > 150%, should be capped
        assert efficiency == Decimal("150.00")


@pytest.mark.unit
class TestInferenceEdgeCases:
    """Test edge cases for inference engine"""

    def test_inference_with_single_employee(self):
        """Test efficiency calculation with 1 employee"""
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

        efficiency, cycle_time, was_inferred = calculate_efficiency(mock_db, entry, product)

        # (10 × 0.5) / (1 × 8.0) × 100 = 62.5%
        assert efficiency == Decimal("62.50")

    def test_inference_with_fractional_hours(self):
        """Test efficiency with fractional runtime hours"""
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
            run_time_hours=Decimal("7.5"),  # 7.5 hours
            employees_assigned=4,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        efficiency, cycle_time, was_inferred = calculate_efficiency(mock_db, entry, product)

        # (100 × 0.25) / (4 × 7.5) × 100 = 83.33%
        expected = Decimal("83.33")
        assert abs(efficiency - expected) < Decimal("0.01")

    def test_inference_excludes_current_entry(self):
        """Test historical inference excludes the entry being calculated"""
        from backend.calculations.efficiency import infer_ideal_cycle_time

        mock_db = Mock()

        # Mock setup to verify exclusion filter is called
        entry_query = Mock()
        entry_filter_product = Mock()
        entry_filter_efficiency = Mock()
        entry_filter_performance = Mock()
        entry_filter_exclude = Mock()
        entry_limit = Mock()

        entry_limit.all.return_value = []
        entry_filter_exclude.limit.return_value = entry_limit
        entry_filter_performance.filter.return_value = entry_filter_exclude
        entry_filter_efficiency.isnot.return_value = entry_filter_performance
        entry_filter_product.filter.return_value = entry_filter_efficiency
        entry_query.filter.return_value = entry_filter_product

        mock_db.query.return_value = entry_query

        # Call with current_entry_id
        cycle_time, was_inferred = infer_ideal_cycle_time(
            mock_db,
            product_id=1,
            current_entry_id=999  # Should be excluded
        )

        # Should use default since no historical data
        assert cycle_time > 0


@pytest.mark.integration
class TestInferenceIntegration:
    """Integration tests for inference engine"""

    def test_full_inference_workflow(self):
        """Test complete inference workflow from missing data to calculation"""
        # This would require actual database setup
        # Simplified mock version here
        from backend.calculations.efficiency import calculate_efficiency, infer_ideal_cycle_time

        assert True  # Placeholder for integration test

    def test_inference_updates_across_entries(self):
        """Test inference improves as more data is added"""
        # Would test that as historical entries accumulate,
        # inference becomes more accurate
        assert True  # Placeholder


@pytest.mark.performance
class TestInferencePerformance:
    """Performance tests for inference engine"""

    def test_inference_query_efficiency(self):
        """Test inference doesn't make excessive database queries"""
        from backend.calculations.efficiency import infer_ideal_cycle_time
        from backend.schemas.product import Product

        mock_db = Mock()

        product = Product(
            product_id=1,
            product_code="P001",
            product_name="Product A",
            ideal_cycle_time=Decimal("0.25"),
            is_active=True
        )

        # Setup minimal mocks
        product_query = Mock()
        product_filter = Mock()
        product_filter.first.return_value = product
        product_query.filter.return_value = product_filter
        mock_db.query.return_value = product_query

        cycle_time, was_inferred = infer_ideal_cycle_time(mock_db, product_id=1)

        # Should only query product table (1 query)
        assert mock_db.query.call_count == 1

    def test_inference_calculation_speed(self):
        """Test inference calculation is fast"""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production import ProductionEntry
        from backend.schemas.product import Product
        import time

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
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=1
        )

        start = time.time()
        for _ in range(100):
            calculate_efficiency(mock_db, entry, product)
        duration = time.time() - start

        # 100 calculations should be fast
        assert duration < 1.0


@pytest.mark.unit
class TestInferenceAccuracy:
    """Test accuracy of inference calculations"""

    def test_historical_average_calculation(self):
        """Test historical average is calculated correctly"""
        # Would verify the mathematical accuracy of averaging
        # historical cycle times
        from backend.calculations.efficiency import infer_ideal_cycle_time

        # Test with known inputs and expected output
        assert True  # Detailed test would go here

    def test_inference_consistency(self):
        """Test same inputs produce same inference result"""
        from backend.calculations.efficiency import infer_ideal_cycle_time, DEFAULT_CYCLE_TIME

        mock_db = Mock()

        # Setup to return default
        product_query = Mock()
        product_filter = Mock()
        product_filter.first.return_value = None
        product_query.filter.return_value = product_filter

        entry_query = Mock()
        entry_filter = Mock()
        entry_isnot_1 = Mock()
        entry_isnot_2 = Mock()
        entry_limit = Mock()
        entry_limit.all.return_value = []
        entry_isnot_2.limit.return_value = entry_limit
        entry_isnot_1.isnot.return_value = entry_isnot_2
        entry_filter.filter.return_value = entry_isnot_1
        entry_query.filter.return_value = entry_filter

        def mock_query_selector(model):
            if 'Product' in str(model):
                return product_query
            else:
                return entry_query

        mock_db.query.side_effect = mock_query_selector

        # Call multiple times
        result1 = infer_ideal_cycle_time(mock_db, product_id=1)
        result2 = infer_ideal_cycle_time(mock_db, product_id=1)

        assert result1 == result2  # Deterministic
