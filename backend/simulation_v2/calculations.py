"""
Production Line Simulation v2.0 - Output Block Calculations

Transforms raw simulation metrics into the 8 structured output blocks.
All functions are pure (no side effects) and stateless.
"""

from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict
import statistics

from .models import (
    SimulationConfig,
    WeeklyDemandCapacityRow,
    DailySummary,
    StationPerformanceRow,
    FreeCapacityAnalysis,
    BundleMetricsRow,
    PerProductSummaryRow,
    RebalancingSuggestionRow,
    AssumptionLog,
    SimulationResults,
    ValidationReport,
    CoverageStatus,
    RebalanceRole,
    DemandMode,
)
from .engine import SimulationMetrics
from .constants import (
    BOTTLENECK_UTILIZATION_THRESHOLD,
    DONOR_UTILIZATION_THRESHOLD,
    COVERAGE_OK_THRESHOLD,
    COVERAGE_TIGHT_THRESHOLD,
    FORMULA_DESCRIPTIONS,
    SIMULATION_LIMITATIONS,
    ENGINE_VERSION,
)


def calculate_all_blocks(
    config: SimulationConfig,
    metrics: SimulationMetrics,
    validation_report: ValidationReport,
    duration_seconds: float,
    defaults_applied: List[Dict[str, Any]] | None = None
) -> SimulationResults:
    """
    Calculate all 8 output blocks from simulation metrics.

    Args:
        config: The simulation configuration that was run
        metrics: Raw metrics collected during simulation
        validation_report: Results from input validation
        duration_seconds: How long the simulation took to run
        defaults_applied: List of defaults that were applied to inputs

    Returns:
        SimulationResults containing all 8 output blocks
    """
    if defaults_applied is None:
        defaults_applied = []

    # Calculate horizon in minutes for utilization calculations
    horizon_minutes = config.schedule.daily_planned_hours * 60 * config.horizon_days

    # Build block data
    weekly_demand_capacity = _calculate_block1_weekly_capacity(config, metrics)
    daily_summary = _calculate_block2_daily_summary(config, metrics)
    station_performance = _calculate_block3_station_performance(
        config, metrics, horizon_minutes
    )
    free_capacity = _calculate_block4_free_capacity(
        config, metrics, station_performance
    )
    bundle_metrics = _calculate_block5_bundle_metrics(config, metrics)
    per_product_summary = _calculate_block6_per_product(config, metrics)
    rebalancing_suggestions = _calculate_block7_rebalancing(
        station_performance, config
    )
    assumption_log = _calculate_block8_assumption_log(config, defaults_applied)

    return SimulationResults(
        weekly_demand_capacity=weekly_demand_capacity,
        daily_summary=daily_summary,
        station_performance=station_performance,
        free_capacity=free_capacity,
        bundle_metrics=bundle_metrics,
        per_product_summary=per_product_summary,
        rebalancing_suggestions=rebalancing_suggestions,
        assumption_log=assumption_log,
        validation_report=validation_report,
        simulation_duration_seconds=duration_seconds
    )


def _calculate_block1_weekly_capacity(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> List[WeeklyDemandCapacityRow]:
    """
    Block 1: Weekly Demand vs Capacity comparison.

    Compares weekly demand targets against simulated weekly capacity
    and classifies each product's status.
    """
    rows = []

    for demand in config.demands:
        product = demand.product

        # Get weekly demand (convert from daily if necessary)
        weekly_demand: float
        if demand.weekly_demand:
            weekly_demand = demand.weekly_demand
        elif demand.daily_demand:
            weekly_demand = demand.daily_demand * config.schedule.work_days
        elif config.mode == DemandMode.MIX_DRIVEN and config.total_demand and demand.mix_share_pct:
            daily = config.total_demand * demand.mix_share_pct / 100
            weekly_demand = daily * config.schedule.work_days
        else:
            continue  # No demand specified

        if weekly_demand <= 0:
            continue

        # Get throughput (scale to weekly if horizon is not 7 days)
        total_throughput = metrics.throughput_by_product.get(product, 0)
        daily_throughput = total_throughput / config.horizon_days
        weekly_capacity = int(daily_throughput * config.schedule.work_days)

        # Calculate coverage percentage
        coverage_pct = (weekly_capacity / weekly_demand * 100) if weekly_demand > 0 else 0

        # Determine status based on thresholds
        if coverage_pct >= COVERAGE_OK_THRESHOLD:
            status = CoverageStatus.OK
        elif coverage_pct >= COVERAGE_TIGHT_THRESHOLD:
            status = CoverageStatus.TIGHT
        else:
            status = CoverageStatus.SHORTFALL

        rows.append(WeeklyDemandCapacityRow(
            product=product,
            weekly_demand_pcs=int(weekly_demand),
            max_weekly_capacity_pcs=weekly_capacity,
            demand_coverage_pct=round(coverage_pct, 1),
            status=status
        ))

    return rows


def _calculate_block2_daily_summary(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> DailySummary:
    """
    Block 2: Daily aggregate summary.

    Provides overall daily metrics including throughput, demand coverage,
    cycle time, and WIP levels.
    """
    # Calculate total throughput
    total_throughput = sum(metrics.throughput_by_product.values())
    daily_throughput = int(total_throughput / config.horizon_days)

    # Calculate total daily demand
    total_daily_demand = 0.0
    for demand in config.demands:
        if demand.daily_demand:
            total_daily_demand += demand.daily_demand
        elif demand.weekly_demand:
            total_daily_demand += demand.weekly_demand / config.schedule.work_days
        elif config.mode == DemandMode.MIX_DRIVEN and config.total_demand and demand.mix_share_pct:
            total_daily_demand += config.total_demand * demand.mix_share_pct / 100

    # Calculate coverage
    coverage_pct = (
        (daily_throughput / total_daily_demand * 100)
        if total_daily_demand > 0 else 0
    )

    # Cycle time statistics
    avg_cycle_time = (
        statistics.mean(metrics.cycle_times)
        if metrics.cycle_times else 0
    )

    # WIP statistics
    avg_wip = (
        statistics.mean(metrics.wip_samples)
        if metrics.wip_samples else 0
    )

    # Determine bundle size string
    bundle_sizes = set(
        d.bundle_size for d in config.demands
        if d.product in metrics.throughput_by_product
    )
    if len(bundle_sizes) == 0:
        bundle_size_str = "1"
    elif len(bundle_sizes) == 1:
        bundle_size_str = str(list(bundle_sizes)[0])
    else:
        bundle_size_str = "mixed"

    return DailySummary(
        total_shifts_per_day=config.schedule.shifts_enabled,
        daily_planned_hours=config.schedule.daily_planned_hours,
        daily_throughput_pcs=daily_throughput,
        daily_demand_pcs=int(total_daily_demand),
        daily_coverage_pct=round(coverage_pct, 1),
        avg_cycle_time_min=round(avg_cycle_time, 1),
        avg_wip_pcs=round(avg_wip, 0),
        bundles_processed_per_day=int(metrics.bundles_completed / config.horizon_days),
        bundle_size_pcs=bundle_size_str
    )


def _calculate_block3_station_performance(
    config: SimulationConfig,
    metrics: SimulationMetrics,
    horizon_minutes: float
) -> List[StationPerformanceRow]:
    """
    Block 3: Per-station/operation performance metrics.

    Calculates utilization, queue times, and bottleneck/donor flags
    for each operation.
    """
    rows = []

    # Calculate total capacity per machine_tool (sum of all operators)
    tool_operators: Dict[str, int] = defaultdict(int)
    for op in config.operations:
        tool_operators[op.machine_tool] += op.operators

    # Track which machine_tools we've already processed to avoid duplicate metrics
    processed_tools: Dict[str, bool] = {}

    for op in config.operations:
        machine_tool = op.machine_tool

        # Get total operators for this tool (pooled capacity)
        total_operators = tool_operators[machine_tool]

        # Available time = horizon × total operators for this tool
        available_minutes = horizon_minutes * total_operators

        # Get metrics for this tool
        busy_time = metrics.station_busy_time.get(machine_tool, 0)
        pieces = metrics.station_pieces_processed.get(machine_tool, 0)
        queue_waits = metrics.station_queue_waits.get(machine_tool, [])

        # Calculate utilization
        util_pct = (
            (busy_time / available_minutes * 100)
            if available_minutes > 0 else 0
        )

        # Average processing time per piece
        avg_process_time = (busy_time / pieces) if pieces > 0 else op.sam_min

        # Average queue wait time
        avg_queue_wait = (
            statistics.mean(queue_waits) if queue_waits else 0
        )

        # Bottleneck/Donor flags
        is_bottleneck = util_pct >= BOTTLENECK_UTILIZATION_THRESHOLD
        is_donor = util_pct <= DONOR_UTILIZATION_THRESHOLD and op.operators > 1

        rows.append(StationPerformanceRow(
            product=op.product,
            step=op.step,
            operation=op.operation,
            machine_tool=machine_tool,
            sequence=op.sequence,
            grouping=op.grouping,
            operators=op.operators,
            total_pieces_processed=pieces,
            total_busy_time_min=round(busy_time, 1),
            avg_processing_time_min=round(avg_process_time, 2),
            util_pct=round(util_pct, 1),
            queue_wait_time_min=round(avg_queue_wait, 1),
            is_bottleneck=is_bottleneck,
            is_donor=is_donor
        ))

    return rows


def _calculate_block4_free_capacity(
    config: SimulationConfig,
    metrics: SimulationMetrics,
    station_performance: List[StationPerformanceRow]
) -> FreeCapacityAnalysis:
    """
    Block 4: Free capacity analysis.

    Analyzes available capacity based on bottleneck utilization and
    calculates equivalent free resources.
    """
    # Find bottleneck utilization (highest utilization station)
    bottleneck_util = max(
        (s.util_pct for s in station_performance),
        default=0
    )

    # Daily figures
    total_throughput = sum(metrics.throughput_by_product.values())
    daily_throughput = total_throughput / config.horizon_days

    # Calculate total daily demand
    total_daily_demand = 0.0
    for d in config.demands:
        if d.daily_demand:
            total_daily_demand += d.daily_demand
        elif d.weekly_demand:
            total_daily_demand += d.weekly_demand / config.schedule.work_days
        elif config.mode == DemandMode.MIX_DRIVEN and config.total_demand and d.mix_share_pct:
            total_daily_demand += config.total_demand * d.mix_share_pct / 100

    # Calculate theoretical max capacity based on bottleneck
    if bottleneck_util > 0:
        daily_max_capacity = int(daily_throughput / (bottleneck_util / 100))
    else:
        daily_max_capacity = int(daily_throughput) if daily_throughput > 0 else 0

    # Demand usage percentage
    demand_usage_pct = (
        (total_daily_demand / daily_max_capacity * 100)
        if daily_max_capacity > 0 else 100
    )

    # Free capacity calculations
    free_pct = max(0, 100 - demand_usage_pct)
    free_line_hours = config.schedule.daily_planned_hours * (free_pct / 100)

    # Free hours at bottleneck
    free_bottleneck_pct = max(0, 100 - bottleneck_util)
    free_bottleneck_hours = config.schedule.daily_planned_hours * (free_bottleneck_pct / 100)

    # Equivalent free operators (based on shift 1 hours as reference)
    equivalent_free_operators = (
        free_bottleneck_hours / config.schedule.shift1_hours
        if config.schedule.shift1_hours > 0 else 0
    )

    return FreeCapacityAnalysis(
        daily_demand_pcs=int(total_daily_demand),
        daily_max_capacity_pcs=daily_max_capacity,
        demand_usage_pct=round(demand_usage_pct, 1),
        free_line_hours_per_day=round(free_line_hours, 2),
        free_operator_hours_at_bottleneck_per_day=round(free_bottleneck_hours, 2),
        equivalent_free_operators_full_shift=round(equivalent_free_operators, 2)
    )


def _calculate_block5_bundle_metrics(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> List[BundleMetricsRow]:
    """
    Block 5: Bundle behavior metrics.

    Provides bundle-level metrics including arrival rates and
    system occupancy.
    """
    rows = []

    for demand in config.demands:
        product = demand.product

        # Skip if no throughput recorded
        if product not in metrics.throughput_by_product:
            continue

        # Calculate daily demand
        daily_demand: float
        if demand.daily_demand:
            daily_demand = demand.daily_demand
        elif demand.weekly_demand:
            daily_demand = demand.weekly_demand / config.schedule.work_days
        elif config.mode == DemandMode.MIX_DRIVEN and config.total_demand and demand.mix_share_pct:
            daily_demand = config.total_demand * demand.mix_share_pct / 100
        else:
            daily_demand = 0

        # Bundles per day
        bundles_per_day = (
            int(daily_demand / demand.bundle_size)
            if demand.bundle_size > 0 else 0
        )

        # Bundle cycle time from product-specific data
        product_cycle_times = metrics.cycle_times_by_product.get(product, [])
        avg_bundle_cycle_time = (
            statistics.mean(product_cycle_times)
            if product_cycle_times else None
        )

        # Bundle system occupancy from samples
        bundle_samples = metrics.bundles_in_system_samples.get(product, [])
        avg_bundles_in_system = (
            statistics.mean(bundle_samples)
            if bundle_samples else None
        )
        max_bundles_in_system = (
            max(bundle_samples)
            if bundle_samples else None
        )

        rows.append(BundleMetricsRow(
            product=product,
            bundle_size_pcs=demand.bundle_size,
            bundles_arriving_per_day=bundles_per_day,
            avg_bundles_in_system=round(avg_bundles_in_system, 1) if avg_bundles_in_system else None,
            max_bundles_in_system=max_bundles_in_system,
            avg_bundle_cycle_time_min=round(avg_bundle_cycle_time, 1) if avg_bundle_cycle_time else None
        ))

    return rows


def _calculate_block6_per_product(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> List[PerProductSummaryRow]:
    """
    Block 6: Per-product summary.

    Provides demand vs throughput comparison for each product
    at both daily and weekly granularity.
    """
    rows = []

    for demand in config.demands:
        product = demand.product
        throughput = metrics.throughput_by_product.get(product, 0)

        # Calculate demands
        daily_demand: float
        if demand.daily_demand:
            daily_demand = demand.daily_demand
        elif demand.weekly_demand:
            daily_demand = demand.weekly_demand / config.schedule.work_days
        elif config.mode == DemandMode.MIX_DRIVEN and config.total_demand and demand.mix_share_pct:
            daily_demand = config.total_demand * demand.mix_share_pct / 100
        else:
            daily_demand = 0

        weekly_demand: float
        if demand.weekly_demand:
            weekly_demand = demand.weekly_demand
        elif demand.daily_demand:
            weekly_demand = demand.daily_demand * config.schedule.work_days
        elif config.mode == DemandMode.MIX_DRIVEN and config.total_demand and demand.mix_share_pct:
            weekly_demand = (config.total_demand * demand.mix_share_pct / 100) * config.schedule.work_days
        else:
            weekly_demand = 0

        # Calculate throughput
        daily_throughput = int(throughput / config.horizon_days)
        weekly_throughput = int(daily_throughput * config.schedule.work_days)

        # Calculate coverage percentages
        daily_coverage = (
            (daily_throughput / daily_demand * 100)
            if daily_demand > 0 else 0
        )
        weekly_coverage = (
            (weekly_throughput / weekly_demand * 100)
            if weekly_demand > 0 else 0
        )

        rows.append(PerProductSummaryRow(
            product=product,
            bundle_size_pcs=demand.bundle_size,
            mix_share_pct=demand.mix_share_pct,
            daily_demand_pcs=int(daily_demand),
            daily_throughput_pcs=daily_throughput,
            daily_coverage_pct=round(daily_coverage, 1),
            weekly_demand_pcs=int(weekly_demand),
            weekly_throughput_pcs=weekly_throughput,
            weekly_coverage_pct=round(weekly_coverage, 1)
        ))

    return rows


def _calculate_block7_rebalancing(
    station_performance: List[StationPerformanceRow],
    config: SimulationConfig
) -> List[RebalancingSuggestionRow]:
    """
    Block 7: Rebalancing suggestions.

    Identifies bottlenecks and potential donor stations, then
    generates operator rebalancing recommendations.
    """
    suggestions = []

    # Find bottlenecks and donors
    bottlenecks = [s for s in station_performance if s.is_bottleneck]
    donors = [s for s in station_performance if s.is_donor]

    # Sort bottlenecks by utilization (highest first)
    bottlenecks.sort(key=lambda x: x.util_pct, reverse=True)

    # Sort donors by utilization (lowest first - most slack)
    donors.sort(key=lambda x: x.util_pct)

    # Pair bottlenecks with donors
    for i, bottleneck in enumerate(bottlenecks):
        # Suggest adding operator to bottleneck
        new_operators = bottleneck.operators + 1
        # Utilization scales inversely with capacity
        new_util = bottleneck.util_pct * bottleneck.operators / new_operators

        suggestions.append(RebalancingSuggestionRow(
            product="ALL",  # Cross-product suggestion
            step=bottleneck.step,
            operation=bottleneck.operation,
            machine_tool=bottleneck.machine_tool,
            grouping=bottleneck.grouping,
            operators_before=bottleneck.operators,
            operators_after=new_operators,
            util_before_pct=bottleneck.util_pct,
            util_after_pct=round(new_util, 1),
            role=RebalanceRole.BOTTLENECK,
            comment="Add 1 operator to reduce bottleneck"
        ))

        # If we have a matching donor, suggest moving operator from donor
        if i < len(donors):
            donor = donors[i]
            if donor.operators > 1:
                new_donor_operators = donor.operators - 1
                new_donor_util = donor.util_pct * donor.operators / new_donor_operators

                suggestions.append(RebalancingSuggestionRow(
                    product="ALL",
                    step=donor.step,
                    operation=donor.operation,
                    machine_tool=donor.machine_tool,
                    grouping=donor.grouping,
                    operators_before=donor.operators,
                    operators_after=new_donor_operators,
                    util_before_pct=donor.util_pct,
                    util_after_pct=round(new_donor_util, 1),
                    role=RebalanceRole.DONOR,
                    comment=f"Move 1 operator to Step {bottleneck.step} ({bottleneck.operation})"
                ))

    return suggestions


def _calculate_block8_assumption_log(
    config: SimulationConfig,
    defaults_applied: List[Dict[str, Any]]
) -> AssumptionLog:
    """
    Block 8: Complete assumption and configuration log.

    Documents all settings, defaults, formulas, and limitations
    for audit and reproducibility.
    """
    return AssumptionLog(
        timestamp=datetime.utcnow(),
        simulation_engine_version=ENGINE_VERSION,
        configuration_mode=config.mode.value,
        schedule={
            "shifts_enabled": config.schedule.shifts_enabled,
            "shift1_hours": config.schedule.shift1_hours,
            "shift2_hours": config.schedule.shift2_hours,
            "shift3_hours": config.schedule.shift3_hours,
            "work_days": config.schedule.work_days,
            "ot_enabled": config.schedule.ot_enabled,
            "weekday_ot_hours": config.schedule.weekday_ot_hours,
            "weekend_ot_days": config.schedule.weekend_ot_days,
            "weekend_ot_hours": config.schedule.weekend_ot_hours,
            "daily_planned_hours": config.schedule.daily_planned_hours,
            "weekly_base_hours": config.schedule.weekly_base_hours,
            "weekly_total_hours": config.schedule.weekly_total_hours,
        },
        products=[
            {
                "product": d.product,
                "bundle_size": d.bundle_size,
                "daily_demand": d.daily_demand,
                "weekly_demand": d.weekly_demand,
                "mix_share_pct": d.mix_share_pct
            }
            for d in config.demands
        ],
        operations_defaults_applied=defaults_applied,
        breakdowns_configuration={
            "enabled": bool(config.breakdowns),
            "count": len(config.breakdowns) if config.breakdowns else 0,
            "message": (
                "Perfect equipment reliability assumed"
                if not config.breakdowns
                else f"{len(config.breakdowns)} breakdown rules configured"
            ),
            "details": [
                {"machine_tool": b.machine_tool, "breakdown_pct": b.breakdown_pct}
                for b in (config.breakdowns or [])
            ]
        },
        formula_implementations=FORMULA_DESCRIPTIONS,
        limitations_and_caveats=SIMULATION_LIMITATIONS
    )
