"""
Production Line Simulation v2.0 - SimPy Discrete-Event Engine

Implements the core simulation logic using SimPy's process-based approach.
Each bundle flows through operations as a generator function, yielding
events for resource requests, timeouts, and state changes.

This module is stateless with no database dependencies.
"""

import simpy
import random
import math
from typing import Dict, List, Tuple, Generator, Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

from .models import (
    SimulationConfig,
    OperationInput,
    VariabilityType,
)
from .constants import (
    SMALL_BUNDLE_THRESHOLD,
    SMALL_BUNDLE_TRANSITION_SECONDS,
    LARGE_BUNDLE_TRANSITION_SECONDS,
    MIN_PROCESS_TIME_MINUTES,
    WIP_SAMPLE_INTERVAL_MINUTES,
    TRIANGULAR_VARIABILITY_MIN,
    TRIANGULAR_VARIABILITY_MAX,
    TRIANGULAR_VARIABILITY_MODE,
)


@dataclass
class SimulationMetrics:
    """Accumulated metrics during simulation run."""

    # Throughput tracking
    throughput_by_product: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    bundles_completed: int = 0

    # Cycle time tracking
    cycle_times: List[float] = field(default_factory=list)
    cycle_times_by_product: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # Station metrics (keyed by machine_tool)
    station_busy_time: Dict[str, float] = field(
        default_factory=lambda: defaultdict(float)
    )
    station_pieces_processed: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    station_queue_waits: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # WIP tracking
    wip_samples: List[int] = field(default_factory=list)
    current_wip: int = 0
    max_wip: int = 0

    # Bundle tracking per product
    bundles_by_product: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    bundles_in_system_samples: Dict[str, List[int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    current_bundles_by_product: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    # Rework tracking
    rework_count: int = 0
    rework_by_station: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    # Breakdown tracking
    breakdown_events: int = 0
    breakdown_time_lost: float = 0.0


class ProductionLineSimulator:
    """
    SimPy-based discrete-event simulation for labor-intensive production lines.

    This simulator models bundles of pieces flowing through a sequence of
    operations, each requiring specific machine/tool resources with pooled
    operator capacity.
    """

    def __init__(self, config: SimulationConfig, seed: int | None = None):
        """
        Initialize the simulator with configuration.

        Args:
            config: Complete simulation configuration
            seed: Optional random seed for reproducibility
        """
        self.config = config

        # Set random seed if provided
        if seed is not None:
            random.seed(seed)

        self.env = simpy.Environment()
        self.metrics = SimulationMetrics()

        # Build data structures
        self.operations_by_product = self._group_operations_by_product()
        self.demands_by_product = {d.product: d for d in config.demands}
        self.breakdowns_by_tool = {
            b.machine_tool: b.breakdown_pct
            for b in (config.breakdowns or [])
        }

        # Create SimPy resources (machine/tool pools)
        self.resources = self._create_resources()

        # Calculate simulation horizon in minutes
        self.horizon_minutes = (
            config.schedule.daily_planned_hours * 60 * config.horizon_days
        )

    def _group_operations_by_product(self) -> Dict[str, List[OperationInput]]:
        """Group operations by product, sorted by step."""
        grouped: Dict[str, List[OperationInput]] = defaultdict(list)
        for op in self.config.operations:
            grouped[op.product].append(op)

        # Sort each product's operations by step
        for product in grouped:
            grouped[product].sort(key=lambda x: x.step)

        return dict(grouped)

    def _create_resources(self) -> Dict[str, simpy.Resource]:
        """
        Create SimPy Resource for each unique machine/tool.

        Resource capacity is the sum of operators across all operations
        that use the same machine/tool (resource pooling).
        """
        # Sum operators across all operations using the same tool
        tool_capacity: Dict[str, int] = defaultdict(int)
        for op in self.config.operations:
            tool_capacity[op.machine_tool] += op.operators

        resources = {}
        for tool, capacity in tool_capacity.items():
            resources[tool] = simpy.Resource(self.env, capacity=capacity)

        return resources

    def _calculate_process_time(self, op: OperationInput) -> float:
        """
        Calculate actual processing time for a single piece.

        Formula: Actual = SAM × (1 + Variability + FPD/100 + (100-Grade)/100)

        Args:
            op: Operation with SAM and adjustment factors

        Returns:
            Processing time in minutes (minimum MIN_PROCESS_TIME_MINUTES)
        """
        base_sam = op.sam_min

        # Variability factor
        if op.variability == VariabilityType.TRIANGULAR:
            # Symmetric triangular distribution centered at 0
            variability_factor = random.triangular(
                TRIANGULAR_VARIABILITY_MIN,
                TRIANGULAR_VARIABILITY_MAX,
                TRIANGULAR_VARIABILITY_MODE
            )
        else:
            variability_factor = 0.0

        # FPD multiplier (directly from percentage)
        fpd_multiplier = op.fpd_pct / 100

        # Grade multiplier (penalty for less than 100% skill)
        grade_multiplier = (100 - op.grade_pct) / 100

        actual_time = base_sam * (1 + variability_factor + fpd_multiplier + grade_multiplier)

        return max(MIN_PROCESS_TIME_MINUTES, actual_time)

    def _get_bundle_transition_time(self, bundle_size: int) -> float:
        """
        Get transition time in minutes based on bundle size.

        Args:
            bundle_size: Number of pieces in the bundle

        Returns:
            Transition time in minutes
        """
        if bundle_size <= SMALL_BUNDLE_THRESHOLD:
            return SMALL_BUNDLE_TRANSITION_SECONDS / 60  # Convert to minutes
        else:
            return LARGE_BUNDLE_TRANSITION_SECONDS / 60  # Convert to minutes

    def _check_breakdown(self, machine_tool: str) -> float:
        """
        Check if a breakdown occurs and return delay time.

        Args:
            machine_tool: The machine/tool to check

        Returns:
            Breakdown delay in minutes (0 if no breakdown)
        """
        breakdown_pct = self.breakdowns_by_tool.get(machine_tool, 0.0)
        if breakdown_pct > 0 and random.random() * 100 < breakdown_pct:
            # Simplified breakdown: fixed 30-minute delay
            # Could be made configurable in future versions
            delay = 30.0
            self.metrics.breakdown_events += 1
            self.metrics.breakdown_time_lost += delay
            return delay
        return 0.0

    def _bundle_process(
        self,
        bundle_id: int,
        product: str,
        bundle_size: int,
        operations: List[OperationInput]
    ) -> Generator[Any, Any, None]:
        """
        Generator function representing a bundle flowing through operations.

        This is the core SimPy process. Each bundle:
        1. Enters the system (WIP increases)
        2. Flows through operations in sequence
        3. At each operation: waits for resource, processes each piece
        4. Exits the system (WIP decreases, throughput recorded)

        Args:
            bundle_id: Unique identifier for this bundle
            product: Product type being produced
            bundle_size: Number of pieces in this bundle
            operations: Ordered list of operations to process
        """
        start_time = self.env.now
        self.metrics.current_wip += bundle_size
        self.metrics.max_wip = max(self.metrics.max_wip, self.metrics.current_wip)
        self.metrics.current_bundles_by_product[product] += 1

        transition_time = self._get_bundle_transition_time(bundle_size)

        for op in operations:
            # Entry transition delay
            yield self.env.timeout(transition_time)

            arrival_time = self.env.now

            # Request the machine/tool resource
            with self.resources[op.machine_tool].request() as request:
                yield request  # Wait for availability

                # Record queue wait time
                wait_time = self.env.now - arrival_time
                self.metrics.station_queue_waits[op.machine_tool].append(wait_time)

                # Check for equipment breakdown
                breakdown_delay = self._check_breakdown(op.machine_tool)
                if breakdown_delay > 0:
                    yield self.env.timeout(breakdown_delay)

                # Process each piece in the bundle
                for piece_idx in range(bundle_size):
                    process_time = self._calculate_process_time(op)
                    yield self.env.timeout(process_time)

                    # Accumulate busy time and piece count
                    self.metrics.station_busy_time[op.machine_tool] += process_time
                    self.metrics.station_pieces_processed[op.machine_tool] += 1

                    # Check for rework requirement
                    if op.rework_pct > 0 and random.random() * 100 < op.rework_pct:
                        self.metrics.rework_count += 1
                        self.metrics.rework_by_station[op.machine_tool] += 1
                        # Rework adds another processing cycle at this station
                        rework_time = self._calculate_process_time(op)
                        yield self.env.timeout(rework_time)
                        self.metrics.station_busy_time[op.machine_tool] += rework_time

            # Exit transition delay
            yield self.env.timeout(transition_time)

        # Bundle completed
        end_time = self.env.now
        cycle_time = end_time - start_time

        self.metrics.cycle_times.append(cycle_time)
        self.metrics.cycle_times_by_product[product].append(cycle_time)
        self.metrics.throughput_by_product[product] += bundle_size
        self.metrics.bundles_completed += 1
        self.metrics.bundles_by_product[product] += 1
        self.metrics.current_wip -= bundle_size
        self.metrics.current_bundles_by_product[product] -= 1

    def _wip_sampler(self, interval_minutes: float = WIP_SAMPLE_INTERVAL_MINUTES) -> Generator[Any, Any, None]:
        """
        Background process to sample WIP periodically.

        Args:
            interval_minutes: Sampling interval in minutes
        """
        while True:
            yield self.env.timeout(interval_minutes)
            self.metrics.wip_samples.append(self.metrics.current_wip)
            # Also sample bundles per product
            for product in self.metrics.current_bundles_by_product:
                self.metrics.bundles_in_system_samples[product].append(
                    self.metrics.current_bundles_by_product[product]
                )

    def _generate_bundles(self) -> None:
        """
        Generate all bundles at simulation start.

        In mix-driven mode, calculates demand from total_demand and mix percentages.
        In demand-driven mode, uses daily/weekly demand values directly.
        """
        from .models import DemandMode

        for product, demand in self.demands_by_product.items():
            if product not in self.operations_by_product:
                continue

            operations = self.operations_by_product[product]
            bundle_size = demand.bundle_size

            # Calculate daily demand based on mode
            if self.config.mode == DemandMode.MIX_DRIVEN:
                # Mix-driven: calculate from total and percentage
                if self.config.total_demand and demand.mix_share_pct:
                    daily_demand = (self.config.total_demand * demand.mix_share_pct / 100)
                else:
                    daily_demand = 0
            else:
                # Demand-driven: use direct values
                daily_demand = demand.daily_demand
                if not daily_demand and demand.weekly_demand:
                    daily_demand = demand.weekly_demand / self.config.schedule.work_days

            if not daily_demand or daily_demand <= 0:
                continue

            # Scale by horizon
            total_demand = daily_demand * self.config.horizon_days

            # Calculate bundles needed (round up to ensure coverage)
            bundles_needed = math.ceil(total_demand / bundle_size)

            # Create bundle processes with staggered start times
            # This prevents all bundles from entering simultaneously
            inter_arrival_time = self.horizon_minutes / bundles_needed if bundles_needed > 0 else 0

            for bundle_id in range(bundles_needed):
                # Calculate start delay (spread bundles across horizon)
                start_delay = bundle_id * inter_arrival_time * 0.1  # 10% spread factor

                self.env.process(
                    self._delayed_bundle_start(
                        start_delay, bundle_id, product, bundle_size, operations
                    )
                )

    def _delayed_bundle_start(
        self,
        delay: float,
        bundle_id: int,
        product: str,
        bundle_size: int,
        operations: List[OperationInput]
    ) -> Generator[Any, Any, None]:
        """
        Start a bundle after an initial delay.

        Args:
            delay: Time to wait before starting
            bundle_id: Bundle identifier
            product: Product type
            bundle_size: Pieces in bundle
            operations: Operations sequence
        """
        if delay > 0:
            yield self.env.timeout(delay)
        yield from self._bundle_process(bundle_id, product, bundle_size, operations)

    def run(self) -> SimulationMetrics:
        """
        Execute the simulation and return collected metrics.

        Returns:
            SimulationMetrics with all accumulated data
        """
        # Start WIP sampler background process
        self.env.process(self._wip_sampler())

        # Generate all bundles
        self._generate_bundles()

        # Run simulation until horizon
        self.env.run(until=self.horizon_minutes)

        return self.metrics


def run_simulation(
    config: SimulationConfig,
    seed: int | None = None
) -> Tuple[SimulationMetrics, float]:
    """
    Execute simulation and return metrics with duration.

    This is the main entry point for running a simulation.

    Args:
        config: Complete simulation configuration
        seed: Optional random seed for reproducibility

    Returns:
        Tuple of (SimulationMetrics, duration_seconds)
    """
    start_time = datetime.now()

    simulator = ProductionLineSimulator(config, seed=seed)
    metrics = simulator.run()

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    return metrics, duration_seconds
