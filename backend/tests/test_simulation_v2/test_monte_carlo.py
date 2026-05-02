"""
Tests for the SimPy V2 Monte Carlo wrapper.

Covers:
  - compute_stat math (mean / std / 95% CI / edge cases)
  - aggregate_runs walks blocks correctly (singletons + list-of-rows)
  - run_monte_carlo seeded reproducibility (same base_seed → same sample_run)
  - Validation short-circuit when config has errors
  - Aggregated stats shape matches what the route emits

These are pure-Python unit tests (no DB, no FastAPI client). The route
integration test sits in `test_integration.py` alongside the existing
`/run` route test.
"""

from typing import List

import pytest

from backend.simulation_v2.models import (
    DemandInput,
    DemandMode,
    OperationInput,
    ScheduleConfig,
    SimulationConfig,
    SimulationResults,
)
from backend.simulation_v2.monte_carlo import (
    aggregate_runs,
    compute_stat,
    run_monte_carlo,
)


# =============================================================================
# compute_stat
# =============================================================================


class TestComputeStat:
    def test_empty_list_returns_zeros(self):
        s = compute_stat([])
        assert s == {"mean": 0.0, "std": 0.0, "ci_lo_95": 0.0, "ci_hi_95": 0.0, "n": 0}

    def test_single_value_zero_variance(self):
        s = compute_stat([42.0])
        assert s["mean"] == 42.0
        assert s["std"] == 0.0
        assert s["ci_lo_95"] == 42.0
        assert s["ci_hi_95"] == 42.0
        assert s["n"] == 1

    def test_constant_values_zero_std(self):
        s = compute_stat([5.0, 5.0, 5.0, 5.0])
        assert s["mean"] == 5.0
        assert s["std"] == 0.0
        assert s["ci_lo_95"] == 5.0
        assert s["ci_hi_95"] == 5.0
        assert s["n"] == 4

    def test_known_distribution_mean_and_ci(self):
        # 10 values, integer mean = 5.5, sample std ≈ 3.0277
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        s = compute_stat(values)
        assert s["n"] == 10
        assert s["mean"] == pytest.approx(5.5, abs=1e-6)
        # standard error = std / sqrt(10) ≈ 0.957
        # half-width = 1.96 * SE ≈ 1.876
        assert s["ci_lo_95"] == pytest.approx(s["mean"] - 1.96 * (s["std"] / (10 ** 0.5)), abs=1e-6)
        assert s["ci_hi_95"] == pytest.approx(s["mean"] + 1.96 * (s["std"] / (10 ** 0.5)), abs=1e-6)
        # CI must bracket the mean
        assert s["ci_lo_95"] < s["mean"] < s["ci_hi_95"]


# =============================================================================
# aggregate_runs
# =============================================================================


def _build_min_results(throughput: int, util: float, product: str = "PRODUCT_A") -> SimulationResults:
    """
    Construct a SimulationResults shell with the minimum populated fields
    needed to exercise the aggregator. Real engine output has dozens of
    populated fields; the aggregator should walk whatever it sees.
    """
    from backend.simulation_v2.models import (
        AssumptionLog,
        BundleMetricsRow,
        CoverageStatus,
        DailySummary,
        FreeCapacityAnalysis,
        PerProductSummaryRow,
        StationPerformanceRow,
        ValidationReport,
        WeeklyDemandCapacityRow,
    )
    from datetime import datetime, timezone

    return SimulationResults(
        weekly_demand_capacity=[
            WeeklyDemandCapacityRow(
                product=product,
                weekly_demand_pcs=1000,
                max_weekly_capacity_pcs=throughput,
                demand_coverage_pct=throughput / 10.0,
                status=CoverageStatus.OK,
            )
        ],
        daily_summary=DailySummary(
            total_shifts_per_day=1,
            daily_planned_hours=8.0,
            daily_throughput_pcs=throughput // 5,
            daily_demand_pcs=200,
            daily_coverage_pct=80.0,
            avg_cycle_time_min=15.0,
            avg_wip_pcs=50.0,
            bundles_processed_per_day=20,
            bundle_size_pcs="10",
        ),
        station_performance=[
            StationPerformanceRow(
                product=product,
                step=1,
                operation="OP1",
                machine_tool="MT1",
                sequence="A",
                grouping="G",
                operators=2,
                total_pieces_processed=throughput,
                total_busy_time_min=400.0,
                avg_processing_time_min=2.0,
                util_pct=util,
                queue_wait_time_min=1.0,
                is_bottleneck=False,
                is_donor=False,
            )
        ],
        free_capacity=FreeCapacityAnalysis(
            daily_demand_pcs=200,
            daily_max_capacity_pcs=300,
            demand_usage_pct=66.0,
            free_line_hours_per_day=2.0,
            free_operator_hours_at_bottleneck_per_day=1.5,
            equivalent_free_operators_full_shift=0.2,
        ),
        bundle_metrics=[
            BundleMetricsRow(
                product=product,
                bundle_size_pcs=10,
                bundles_arriving_per_day=20,
                avg_bundles_in_system=5.0,
                max_bundles_in_system=10,
                avg_bundle_cycle_time_min=15.0,
            )
        ],
        per_product_summary=[
            PerProductSummaryRow(
                product=product,
                bundle_size_pcs=10,
                mix_share_pct=100.0,
                daily_demand_pcs=200,
                daily_throughput_pcs=throughput // 5,
                daily_coverage_pct=80.0,
                weekly_demand_pcs=1000,
                weekly_throughput_pcs=throughput,
                weekly_coverage_pct=throughput / 10.0,
            )
        ],
        rebalancing_suggestions=[],
        assumption_log=AssumptionLog(
            timestamp=datetime.now(tz=timezone.utc),
            configuration_mode="DEMAND_DRIVEN",
            schedule={},
            products=[],
            operations_defaults_applied=[],
            breakdowns_configuration={},
            formula_implementations={},
            limitations_and_caveats=[],
        ),
        validation_report=ValidationReport(),
        simulation_duration_seconds=0.5,
    )


class TestAggregateRuns:
    def test_empty_runs_returns_empty_dict(self):
        assert aggregate_runs([]) == {}

    def test_singleton_block_aggregates_numeric_fields(self):
        runs = [
            _build_min_results(throughput=900, util=70.0),
            _build_min_results(throughput=1000, util=75.0),
            _build_min_results(throughput=1100, util=80.0),
        ]
        agg = aggregate_runs(runs)

        assert "daily_summary" in agg
        ds = agg["daily_summary"]
        # daily_throughput_pcs is numeric → stat dict
        assert isinstance(ds["daily_throughput_pcs"], dict)
        assert ds["daily_throughput_pcs"]["n"] == 3
        # mean of 900/5, 1000/5, 1100/5 = 200
        assert ds["daily_throughput_pcs"]["mean"] == pytest.approx(200.0, abs=1e-6)
        # bundle_size_pcs is a string → carried through as-is
        assert ds["bundle_size_pcs"] == "10"

    def test_list_block_groups_by_natural_key(self):
        runs = [
            _build_min_results(throughput=1000, util=70.0, product="A"),
            _build_min_results(throughput=1100, util=75.0, product="A"),
            _build_min_results(throughput=900, util=80.0, product="A"),
        ]
        agg = aggregate_runs(runs)

        # weekly_demand_capacity is keyed by `product`. All three runs have
        # one row for product=A → aggregated into a single grouped row.
        wdc = agg["weekly_demand_capacity"]
        assert isinstance(wdc, list)
        assert len(wdc) == 1
        assert wdc[0]["product"] == "A"
        cap = wdc[0]["max_weekly_capacity_pcs"]
        assert cap["n"] == 3
        assert cap["mean"] == pytest.approx(1000.0, abs=1e-6)

    def test_list_block_handles_mixed_products(self):
        # Same product across runs but a second product appears only in one
        # run — its stat should reflect n=1 not 3.
        from backend.simulation_v2.models import (
            CoverageStatus,
            WeeklyDemandCapacityRow,
        )

        runs = [
            _build_min_results(throughput=1000, util=70.0, product="A"),
            _build_min_results(throughput=1100, util=75.0, product="A"),
            _build_min_results(throughput=900, util=80.0, product="A"),
        ]
        # Inject an extra row only into run #2.
        runs[1].weekly_demand_capacity.append(
            WeeklyDemandCapacityRow(
                product="B",
                weekly_demand_pcs=500,
                max_weekly_capacity_pcs=400,
                demand_coverage_pct=80.0,
                status=CoverageStatus.OK,
            )
        )
        agg = aggregate_runs(runs)
        wdc = agg["weekly_demand_capacity"]
        by_product = {row["product"]: row for row in wdc}
        assert by_product["A"]["max_weekly_capacity_pcs"]["n"] == 3
        assert by_product["B"]["max_weekly_capacity_pcs"]["n"] == 1


# =============================================================================
# run_monte_carlo (end-to-end through the engine)
# =============================================================================


@pytest.fixture
def fast_config(simple_operations: List[OperationInput]) -> SimulationConfig:
    """A small config that runs cheaply enough for multi-replication tests."""
    return SimulationConfig(
        operations=simple_operations,
        schedule=ScheduleConfig(
            shifts_enabled=1,
            shift1_hours=4.0,
            shift2_hours=0.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False,
        ),
        demands=[DemandInput(product="PRODUCT_A", bundle_size=10, daily_demand=50)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


class TestRunMonteCarlo:
    def test_seeded_reproducibility(self, fast_config: SimulationConfig):
        """Same base_seed produces identical sample_run between two MC calls."""
        a = run_monte_carlo(fast_config, n_replications=3, base_seed=42)
        b = run_monte_carlo(fast_config, n_replications=3, base_seed=42)
        assert a["sample_run"].daily_summary.daily_throughput_pcs == \
            b["sample_run"].daily_summary.daily_throughput_pcs

    def test_different_seeds_produce_variation(self, fast_config: SimulationConfig):
        """At least one stat has nonzero std across replications with different seeds."""
        result = run_monte_carlo(fast_config, n_replications=5, base_seed=100)
        ds = result["aggregated_stats"]["daily_summary"]
        # At least one of the numeric fields should have non-zero std across
        # 5 replications (the engine has stochastic variability + breakdowns).
        nonzero_std = any(
            isinstance(v, dict) and v.get("std", 0) > 0 for v in ds.values()
        )
        assert nonzero_std, (
            "Expected at least one numeric stat to vary across replications; "
            f"got daily_summary={ds!r}"
        )

    def test_returns_validation_report(self, fast_config: SimulationConfig):
        result = run_monte_carlo(fast_config, n_replications=2, base_seed=1)
        assert "validation_report" in result
        assert not result["validation_report"].has_errors

    def test_validation_failure_short_circuits(self, simple_operations: List[OperationInput]):
        """Domain-invalid config (demand for an undefined product) → bail
        early with the error report, no replications attempted."""
        bad = SimulationConfig(
            operations=simple_operations,
            schedule=ScheduleConfig(
                shifts_enabled=1, shift1_hours=8.0, shift2_hours=0.0,
                shift3_hours=0.0, work_days=5, ot_enabled=False,
            ),
            # PRODUCT_Z has no operations — product_consistency error.
            demands=[DemandInput(product="PRODUCT_Z", bundle_size=10, daily_demand=50)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        result = run_monte_carlo(bad, n_replications=5, base_seed=1)
        assert result["validation_report"].has_errors
        assert result["sample_run"] is None
        assert result["aggregated_stats"] == {}
        assert result["n_replications"] == 0

    def test_per_run_durations_recorded(self, fast_config: SimulationConfig):
        result = run_monte_carlo(fast_config, n_replications=4, base_seed=7)
        durations = result["per_run_duration_seconds"]
        assert len(durations) == 4
        assert all(d > 0 for d in durations)

    def test_aggregated_stats_shape(self, fast_config: SimulationConfig):
        result = run_monte_carlo(fast_config, n_replications=3, base_seed=3)
        agg = result["aggregated_stats"]
        # All six numeric blocks present.
        for block in (
            "daily_summary",
            "free_capacity",
            "weekly_demand_capacity",
            "station_performance",
            "bundle_metrics",
            "per_product_summary",
        ):
            assert block in agg, f"missing block {block} in aggregated_stats"
