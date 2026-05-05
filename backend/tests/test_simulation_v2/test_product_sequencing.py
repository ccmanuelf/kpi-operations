"""
Tests for Pattern 3 — product sequencing.

Edge cases explicitly covered:
  - n_products == 1 : helper short-circuits without invoking MZ.
  - All setup_times = 0 : MZ still runs but order is degenerate (any
    permutation has the same makespan).
  - Asymmetric setup matrix : a→b ≠ b→a is honoured.
  - Stale entries : setup-time entries for products NOT in the config
    are logged + ignored (not raised).
  - Missing pairs : default to 0.
  - Self-loops in the entries list are ignored.
  - apply via _build_setup_matrix is sensitive to the row/column order
    of `products` (the demands list).

Tests requiring the MiniZinc binary are decorated with `@needs_minizinc`
so CI without MZ skips cleanly.
"""

from typing import List

import pytest

from backend.simulation_v2.models import (
    DemandInput,
    DemandMode,
    OperationInput,
    ScheduleConfig,
    SimulationConfig,
    VariabilityType,
)
from backend.simulation_v2.optimization import is_minizinc_available
from backend.simulation_v2.optimization.product_sequencing import (
    _build_setup_matrix,
    estimate_production_time_minutes,
    sequence_products,
)


needs_minizinc = pytest.mark.skipif(
    not is_minizinc_available(),
    reason="MiniZinc CLI not available",
)


# =============================================================================
# Fixtures
# =============================================================================


def _op(
    *,
    product: str,
    step: int,
    operation: str,
    machine_tool: str,
    sam_min: float,
    operators: int = 1,
    grade_pct: int = 90,
) -> OperationInput:
    return OperationInput(
        product=product,
        step=step,
        operation=operation,
        machine_tool=machine_tool,
        sam_min=sam_min,
        operators=operators,
        variability=VariabilityType.TRIANGULAR,
        rework_pct=0,
        grade_pct=grade_pct,
        fpd_pct=10,
    )


@pytest.fixture
def schedule() -> ScheduleConfig:
    return ScheduleConfig(
        shifts_enabled=1,
        shift1_hours=8,
        shift2_hours=0,
        shift3_hours=0,
        work_days=5,
        ot_enabled=False,
    )


@pytest.fixture
def single_product_config(schedule) -> SimulationConfig:
    return SimulationConfig(
        operations=[
            _op(product="A", step=1, operation="Cut", machine_tool="M1", sam_min=2.0, operators=1, grade_pct=90),
            _op(product="A", step=2, operation="Sew", machine_tool="M2", sam_min=3.0, operators=1, grade_pct=85),
        ],
        schedule=schedule,
        demands=[DemandInput(product="A", bundle_size=10, daily_demand=100)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


@pytest.fixture
def three_product_config(schedule) -> SimulationConfig:
    """Three distinct products with their own ops."""
    ops: List[OperationInput] = []
    for product, sam in [("A", 2.0), ("B", 1.5), ("C", 3.0)]:
        ops.append(
            _op(
                product=product,
                step=1,
                operation=f"Cut-{product}",
                machine_tool="M1",
                sam_min=sam,
                operators=1,
                grade_pct=90,
            )
        )
        ops.append(
            _op(
                product=product,
                step=2,
                operation=f"Sew-{product}",
                machine_tool="M2",
                sam_min=sam * 1.5,
                operators=1,
                grade_pct=85,
            )
        )
    return SimulationConfig(
        operations=ops,
        schedule=schedule,
        demands=[
            DemandInput(product="A", bundle_size=10, daily_demand=100),
            DemandInput(product="B", bundle_size=10, daily_demand=80),
            DemandInput(product="C", bundle_size=10, daily_demand=60),
        ],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


# =============================================================================
# Production-time helper
# =============================================================================


class TestEstimateProductionTimeMinutes:
    def test_uses_bottleneck_rate(self, three_product_config):
        # Product A: ops sam=2.0 + 3.0; bottleneck is 3.0 → 1/3 pcs/min
        # 100 pcs at grade 85% = 100 / (1 * (1/3) * 0.85) ≈ 352.94 → ceil 353
        minutes = estimate_production_time_minutes(three_product_config, "A")
        assert minutes == 353

    def test_returns_zero_for_zero_demand(self, schedule):
        config = SimulationConfig(
            operations=[_op(product="A", step=1, operation="Op", machine_tool="M1", sam_min=1.0)],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=1, daily_demand=0)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        assert estimate_production_time_minutes(config, "A") == 0

    def test_returns_zero_for_unknown_product(self, three_product_config):
        assert estimate_production_time_minutes(three_product_config, "ZZ") == 0


# =============================================================================
# Setup-matrix marshalling
# =============================================================================


class TestBuildSetupMatrix:
    def test_dense_matrix_in_demand_order(self):
        products = ["A", "B", "C"]
        entries = [
            {"from_product": "A", "to_product": "B", "setup_minutes": 10},
            {"from_product": "B", "to_product": "A", "setup_minutes": 20},
            {"from_product": "A", "to_product": "C", "setup_minutes": 30},
        ]
        m = _build_setup_matrix(products, entries)
        # 3x3, diagonals zero.
        assert len(m) == 3 and all(len(r) == 3 for r in m)
        assert m[0][0] == 0 and m[1][1] == 0 and m[2][2] == 0
        assert m[0][1] == 10  # A→B
        assert m[1][0] == 20  # B→A (asymmetric)
        assert m[0][2] == 30  # A→C
        # Missing pairs default to 0.
        assert m[2][0] == 0  # C→A unspecified

    def test_unknown_products_logged_and_ignored(self, caplog):
        products = ["A", "B"]
        entries = [
            {"from_product": "A", "to_product": "B", "setup_minutes": 5},
            {"from_product": "ZZ", "to_product": "A", "setup_minutes": 99},
            {"from_product": "A", "to_product": "QQ", "setup_minutes": 88},
        ]
        with caplog.at_level("WARNING"):
            m = _build_setup_matrix(products, entries)
        assert m[0][1] == 5
        assert m[1][0] == 0  # B→A defaults
        # Two warnings expected, one per stale entry.
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) >= 2

    def test_self_loops_ignored(self):
        products = ["A"]
        entries = [{"from_product": "A", "to_product": "A", "setup_minutes": 999}]
        m = _build_setup_matrix(products, entries)
        assert m == [[0]]

    def test_missing_setup_minutes_defaults_zero(self):
        products = ["A", "B"]
        entries = [{"from_product": "A", "to_product": "B"}]  # no minutes key
        m = _build_setup_matrix(products, entries)
        assert m[0][1] == 0


# =============================================================================
# Single-product short-circuit (no MZ call)
# =============================================================================


class TestSingleProductShortCircuit:
    def test_returns_trivial_schedule_without_solver(self, single_product_config):
        result = sequence_products(single_product_config, setup_entries=[])
        assert result.is_optimal is True
        assert result.is_satisfied is True
        assert result.status == "single-product"
        assert len(result.sequence) == 1
        assert result.sequence[0].position == 1
        assert result.sequence[0].product == "A"
        assert result.sequence[0].setup_from_previous_minutes == 0
        assert result.makespan_minutes == result.total_production_minutes
        assert result.total_setup_minutes == 0


# =============================================================================
# Real-solver tests
# =============================================================================


@needs_minizinc
class TestSequenceProducts:
    def test_three_products_minimizes_makespan(self, three_product_config):
        # Asymmetric setups: A→B cheap, others expensive.
        entries = [
            {"from_product": "A", "to_product": "B", "setup_minutes": 5},
            {"from_product": "B", "to_product": "A", "setup_minutes": 60},
            {"from_product": "A", "to_product": "C", "setup_minutes": 60},
            {"from_product": "C", "to_product": "A", "setup_minutes": 60},
            {"from_product": "B", "to_product": "C", "setup_minutes": 5},
            {"from_product": "C", "to_product": "B", "setup_minutes": 60},
        ]
        result = sequence_products(three_product_config, setup_entries=entries)
        assert result.is_satisfied
        assert result.is_optimal
        assert len(result.sequence) == 3
        # The cheapest path is A→B→C (5 + 5 = 10 min of setup); any other
        # permutation pays at least 60 min on at least one transition.
        names = [s.product for s in result.sequence]
        assert names == ["A", "B", "C"]
        assert result.total_setup_minutes == 10
        # First position has zero setup.
        assert result.sequence[0].setup_from_previous_minutes == 0
        assert result.sequence[1].setup_from_previous_minutes == 5
        assert result.sequence[2].setup_from_previous_minutes == 5

    def test_all_zero_setups_returns_some_valid_permutation(self, three_product_config):
        result = sequence_products(three_product_config, setup_entries=[])
        assert result.is_satisfied
        assert result.is_optimal
        assert result.total_setup_minutes == 0
        # Order is arbitrary (degenerate); just verify it's a permutation.
        names = [s.product for s in result.sequence]
        assert sorted(names) == ["A", "B", "C"]
        # Makespan should equal sum of production times.
        assert result.makespan_minutes == result.total_production_minutes

    def test_asymmetric_matrix_picks_cheapest_direction(self, three_product_config):
        # B→A is cheap (1), every other transition is 100. Optimal start
        # order should put B first so the only transition is B→A→...
        entries = [
            {"from_product": "A", "to_product": "B", "setup_minutes": 100},
            {"from_product": "B", "to_product": "A", "setup_minutes": 1},
            {"from_product": "A", "to_product": "C", "setup_minutes": 100},
            {"from_product": "C", "to_product": "A", "setup_minutes": 100},
            {"from_product": "B", "to_product": "C", "setup_minutes": 100},
            {"from_product": "C", "to_product": "B", "setup_minutes": 100},
        ]
        result = sequence_products(three_product_config, setup_entries=entries)
        assert result.is_satisfied
        names = [s.product for s in result.sequence]
        # Optimal should include the B→A transition (= 1 min), so B
        # immediately precedes A. With A→? being expensive, optimal is
        # B → A → C? (1 + 100 = 101) vs e.g. C → B → A (100 + 1 = 101) —
        # both yield 101 min of setup. Just assert the cheap direction
        # is used.
        for k in range(len(names) - 1):
            if names[k] == "B" and names[k + 1] == "A":
                break
        else:
            pytest.fail("Optimal sequence should use the cheap B→A direction")

    def test_stale_entries_tolerated(self, three_product_config):
        entries = [
            {"from_product": "A", "to_product": "B", "setup_minutes": 5},
            # Stale entries — products not in the config:
            {"from_product": "X", "to_product": "Y", "setup_minutes": 999},
            {"from_product": "Z", "to_product": "A", "setup_minutes": 999},
        ]
        # Should not raise; should ignore the stale entries.
        result = sequence_products(three_product_config, setup_entries=entries)
        assert result.is_satisfied

    def test_makespan_is_start_plus_last_production(self, three_product_config):
        """Verify the schedule arithmetic: end[k] = start[k] + production[k]
        and start[k+1] = end[k] + setup_from_previous[k+1]."""
        entries = [
            {"from_product": "A", "to_product": "B", "setup_minutes": 7},
            {"from_product": "B", "to_product": "C", "setup_minutes": 11},
            {"from_product": "A", "to_product": "C", "setup_minutes": 13},
            {"from_product": "C", "to_product": "A", "setup_minutes": 17},
            {"from_product": "B", "to_product": "A", "setup_minutes": 19},
            {"from_product": "C", "to_product": "B", "setup_minutes": 23},
        ]
        result = sequence_products(three_product_config, setup_entries=entries)
        assert result.is_satisfied
        # First position starts at 0.
        assert result.sequence[0].start_time_minutes == 0
        for k, sp in enumerate(result.sequence):
            assert sp.end_time_minutes == sp.start_time_minutes + sp.production_time_minutes
            if k > 0:
                prev = result.sequence[k - 1]
                assert sp.start_time_minutes == prev.end_time_minutes + sp.setup_from_previous_minutes
        # Makespan equals last position's end time.
        assert result.makespan_minutes == result.sequence[-1].end_time_minutes
