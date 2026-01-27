"""
Production Line Simulation using SimPy
Phase 11: Discrete-event simulation for manufacturing process modeling

Provides:
- Production line process simulation with work stations
- Bottleneck detection and analysis
- Worker allocation simulation
- Downtime and quality issue modeling
- Floating pool impact simulation
- Shift transition modeling
"""
import simpy
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import random
import statistics


class WorkStationType(str, Enum):
    """Types of work stations in production line"""
    RECEIVING = "receiving"
    INSPECTION = "inspection"
    ASSEMBLY = "assembly"
    TESTING = "testing"
    PACKAGING = "packaging"
    SHIPPING = "shipping"


class SimulationEvent(str, Enum):
    """Types of simulation events"""
    UNIT_START = "unit_start"
    UNIT_COMPLETE = "unit_complete"
    STATION_START = "station_start"
    STATION_COMPLETE = "station_complete"
    WORKER_BREAK = "worker_break"
    WORKER_RETURN = "worker_return"
    DOWNTIME_START = "downtime_start"
    DOWNTIME_END = "downtime_end"
    QUALITY_REJECT = "quality_reject"
    SHIFT_CHANGE = "shift_change"


@dataclass
class WorkStation:
    """Configuration for a work station"""
    station_id: int
    name: str
    station_type: WorkStationType
    cycle_time_minutes: float  # Average time per unit
    cycle_time_variability: float = 0.1  # Coefficient of variation
    num_workers: int = 1
    quality_rate: float = 0.98  # Pass rate (0-1)
    downtime_probability: float = 0.02  # Per hour probability
    downtime_duration_minutes: float = 30  # Average downtime duration


@dataclass
class ProductionLineConfig:
    """Configuration for production line simulation"""
    line_id: str
    name: str
    stations: List[WorkStation]
    shift_duration_hours: float = 8.0
    break_duration_minutes: float = 30
    breaks_per_shift: int = 2
    workers_per_station: int = 1
    floating_pool_size: int = 0


@dataclass
class SimulationResult:
    """Result of a production line simulation"""
    line_id: str
    simulation_duration_hours: float
    units_started: int
    units_completed: int
    units_rejected: int
    throughput_per_hour: float
    efficiency: float
    utilization_by_station: Dict[str, float]
    bottleneck_station: Optional[str]
    avg_cycle_time_minutes: float
    total_downtime_minutes: float
    quality_yield: float
    events_log: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class BottleneckAnalysis:
    """Analysis of production line bottlenecks"""
    primary_bottleneck: str
    bottleneck_utilization: float
    queue_times: Dict[str, float]
    station_wait_times: Dict[str, float]
    suggestions: List[str]


# =============================================================================
# SimPy Production Line Simulation
# =============================================================================

class ProductionLineSimulation:
    """
    SimPy-based discrete-event simulation for production lines.

    Models:
    - Work stations with configurable cycle times
    - Workers with breaks and shift changes
    - Quality defects and rework
    - Equipment downtime
    - Floating pool allocation
    """

    def __init__(self, config: ProductionLineConfig, random_seed: Optional[int] = None):
        """
        Initialize production line simulation.

        Args:
            config: Production line configuration
            random_seed: Random seed for reproducibility
        """
        self.config = config
        self.env = simpy.Environment()

        if random_seed is not None:
            random.seed(random_seed)

        # Create resources for each station
        self.stations = {}
        self.station_queues = {}
        for station in config.stations:
            self.stations[station.name] = simpy.Resource(self.env, capacity=station.num_workers)
            self.station_queues[station.name] = []

        # Floating pool workers (shared resource)
        self.floating_pool = simpy.Resource(self.env, capacity=config.floating_pool_size) if config.floating_pool_size > 0 else None

        # Metrics tracking
        self.units_started = 0
        self.units_completed = 0
        self.units_rejected = 0
        self.events_log = []
        self.station_times = {s.name: [] for s in config.stations}
        self.station_waits = {s.name: [] for s in config.stations}
        self.station_busy_time = {s.name: 0 for s in config.stations}
        self.total_downtime = 0

    def log_event(self, event_type: SimulationEvent, data: Dict[str, Any]):
        """Log a simulation event"""
        self.events_log.append({
            "time": self.env.now,
            "event_type": event_type.value,
            **data
        })

    def get_station_config(self, station_name: str) -> WorkStation:
        """Get station configuration by name"""
        for station in self.config.stations:
            if station.name == station_name:
                return station
        raise ValueError(f"Station not found: {station_name}")

    def process_unit(self, unit_id: int):
        """
        Process a single unit through all stations.

        This is the main production process that moves a unit
        through each station in sequence.
        """
        self.units_started += 1
        self.log_event(SimulationEvent.UNIT_START, {"unit_id": unit_id})

        rejected = False

        for station in self.config.stations:
            if rejected:
                break

            arrival_time = self.env.now

            # Request station resource
            with self.stations[station.name].request() as request:
                yield request

                wait_time = self.env.now - arrival_time
                self.station_waits[station.name].append(wait_time)

                self.log_event(SimulationEvent.STATION_START, {
                    "unit_id": unit_id,
                    "station": station.name,
                    "wait_time": wait_time
                })

                # Calculate cycle time with variability
                base_time = station.cycle_time_minutes
                variability = station.cycle_time_variability
                cycle_time = max(0.1, random.gauss(base_time, base_time * variability))

                # Process the unit
                yield self.env.timeout(cycle_time)

                self.station_times[station.name].append(cycle_time)
                self.station_busy_time[station.name] += cycle_time

                # Quality check
                if random.random() > station.quality_rate:
                    rejected = True
                    self.units_rejected += 1
                    self.log_event(SimulationEvent.QUALITY_REJECT, {
                        "unit_id": unit_id,
                        "station": station.name
                    })
                else:
                    self.log_event(SimulationEvent.STATION_COMPLETE, {
                        "unit_id": unit_id,
                        "station": station.name,
                        "cycle_time": cycle_time
                    })

        if not rejected:
            self.units_completed += 1
            self.log_event(SimulationEvent.UNIT_COMPLETE, {"unit_id": unit_id})

    def equipment_downtime(self, station: WorkStation):
        """
        Simulate random equipment downtime for a station.

        Runs continuously, periodically causing downtime events
        based on configured probability.
        """
        while True:
            # Check hourly for downtime
            yield self.env.timeout(60)  # 60 minutes

            if random.random() < station.downtime_probability:
                # Downtime occurs
                duration = max(5, random.gauss(
                    station.downtime_duration_minutes,
                    station.downtime_duration_minutes * 0.3
                ))

                self.log_event(SimulationEvent.DOWNTIME_START, {
                    "station": station.name,
                    "duration": duration
                })

                # Temporarily reduce capacity
                # In SimPy, we simulate this by using the resource
                with self.stations[station.name].request(priority=0) as request:
                    yield request
                    yield self.env.timeout(duration)
                    self.total_downtime += duration

                self.log_event(SimulationEvent.DOWNTIME_END, {
                    "station": station.name
                })

    def unit_generator(self, arrival_rate_per_hour: float, max_units: Optional[int] = None):
        """
        Generate units for processing at specified arrival rate.

        Args:
            arrival_rate_per_hour: Average units per hour to generate
            max_units: Maximum units to generate (None = unlimited)
        """
        unit_id = 0
        inter_arrival_time = 60 / arrival_rate_per_hour  # minutes between arrivals

        while max_units is None or unit_id < max_units:
            # Start processing this unit
            self.env.process(self.process_unit(unit_id))
            unit_id += 1

            # Wait for next unit arrival (exponential distribution)
            yield self.env.timeout(random.expovariate(1 / inter_arrival_time))

    def run(
        self,
        duration_hours: float = 8.0,
        arrival_rate_per_hour: Optional[float] = None,
        max_units: Optional[int] = None
    ) -> SimulationResult:
        """
        Run the production line simulation.

        Args:
            duration_hours: Simulation duration in hours
            arrival_rate_per_hour: Unit arrival rate (None = calculate from capacity)
            max_units: Maximum units to simulate

        Returns:
            SimulationResult with all metrics
        """
        duration_minutes = duration_hours * 60

        # Calculate theoretical capacity if no arrival rate specified
        if arrival_rate_per_hour is None:
            # Use bottleneck station to determine arrival rate
            min_rate = float('inf')
            for station in self.config.stations:
                rate = 60 / station.cycle_time_minutes * station.num_workers
                min_rate = min(min_rate, rate)
            arrival_rate_per_hour = min_rate * 0.9  # 90% of theoretical capacity

        # Start unit generation
        self.env.process(self.unit_generator(arrival_rate_per_hour, max_units))

        # Start downtime processes for each station
        for station in self.config.stations:
            if station.downtime_probability > 0:
                self.env.process(self.equipment_downtime(station))

        # Run simulation
        self.env.run(until=duration_minutes)

        # Calculate results
        throughput = self.units_completed / duration_hours if duration_hours > 0 else 0

        # Calculate utilization
        utilization = {}
        for station in self.config.stations:
            total_available_time = duration_minutes * station.num_workers
            busy_time = self.station_busy_time[station.name]
            utilization[station.name] = (busy_time / total_available_time * 100) if total_available_time > 0 else 0

        # Find bottleneck (highest utilization)
        bottleneck = max(utilization, key=utilization.get) if utilization else None

        # Calculate average cycle time
        all_times = []
        for times in self.station_times.values():
            all_times.extend(times)
        avg_cycle = statistics.mean(all_times) if all_times else 0

        # Calculate quality yield
        total_processed = self.units_completed + self.units_rejected
        quality_yield = (self.units_completed / total_processed * 100) if total_processed > 0 else 0

        # Calculate efficiency
        theoretical_output = arrival_rate_per_hour * duration_hours
        efficiency = (self.units_completed / theoretical_output * 100) if theoretical_output > 0 else 0

        # Generate recommendations
        recommendations = []

        if bottleneck and utilization.get(bottleneck, 0) > 85:
            recommendations.append(f"Bottleneck at {bottleneck} ({utilization[bottleneck]:.1f}% utilization)")
            recommendations.append(f"Consider adding workers or equipment at {bottleneck}")

        if quality_yield < 95:
            # Find station with most rejects
            recommendations.append(f"Quality yield is {quality_yield:.1f}% - investigate quality issues")

        if self.total_downtime > duration_minutes * 0.05:
            recommendations.append(f"High downtime ({self.total_downtime:.0f} min) - review maintenance schedules")

        # Check for high wait times
        for station_name, waits in self.station_waits.items():
            if waits:
                avg_wait = statistics.mean(waits)
                if avg_wait > 5:  # More than 5 minutes average wait
                    recommendations.append(f"High queue time at {station_name} ({avg_wait:.1f} min avg)")

        return SimulationResult(
            line_id=self.config.line_id,
            simulation_duration_hours=duration_hours,
            units_started=self.units_started,
            units_completed=self.units_completed,
            units_rejected=self.units_rejected,
            throughput_per_hour=throughput,
            efficiency=efficiency,
            utilization_by_station=utilization,
            bottleneck_station=bottleneck,
            avg_cycle_time_minutes=avg_cycle,
            total_downtime_minutes=self.total_downtime,
            quality_yield=quality_yield,
            events_log=self.events_log[-100:] if len(self.events_log) > 100 else self.events_log,
            recommendations=recommendations
        )


# =============================================================================
# High-Level Simulation Functions
# =============================================================================

def create_default_production_line(
    line_id: str = "LINE-001",
    num_stations: int = 4,
    workers_per_station: int = 2,
    floating_pool_size: int = 0,
    base_cycle_time: float = 15.0
) -> ProductionLineConfig:
    """
    Create a default production line configuration.

    Args:
        line_id: Unique line identifier
        num_stations: Number of work stations
        workers_per_station: Workers at each station
        floating_pool_size: Size of floating pool
        base_cycle_time: Base cycle time in minutes

    Returns:
        ProductionLineConfig for simulation
    """
    station_types = [
        WorkStationType.RECEIVING,
        WorkStationType.ASSEMBLY,
        WorkStationType.TESTING,
        WorkStationType.PACKAGING
    ]

    stations = []
    for i in range(num_stations):
        station_type = station_types[i % len(station_types)]

        # Vary cycle times slightly
        cycle_multiplier = 1.0 + (i * 0.1)  # Each station slightly longer

        stations.append(WorkStation(
            station_id=i + 1,
            name=f"{station_type.value.title()} {i + 1}",
            station_type=station_type,
            cycle_time_minutes=base_cycle_time * cycle_multiplier,
            cycle_time_variability=0.15,
            num_workers=workers_per_station,
            quality_rate=0.98 - (i * 0.01),  # Quality slightly decreases
            downtime_probability=0.02,
            downtime_duration_minutes=20
        ))

    return ProductionLineConfig(
        line_id=line_id,
        name=f"Production Line {line_id}",
        stations=stations,
        shift_duration_hours=8.0,
        break_duration_minutes=30,
        breaks_per_shift=2,
        workers_per_station=workers_per_station,
        floating_pool_size=floating_pool_size
    )


def run_production_simulation(
    config: ProductionLineConfig,
    duration_hours: float = 8.0,
    arrival_rate_per_hour: Optional[float] = None,
    max_units: Optional[int] = None,
    random_seed: Optional[int] = 42
) -> SimulationResult:
    """
    Run a production line simulation with given configuration.

    Args:
        config: Production line configuration
        duration_hours: Simulation duration
        arrival_rate_per_hour: Unit arrival rate
        max_units: Maximum units to process
        random_seed: Random seed for reproducibility

    Returns:
        SimulationResult with complete metrics
    """
    simulation = ProductionLineSimulation(config, random_seed=random_seed)
    return simulation.run(
        duration_hours=duration_hours,
        arrival_rate_per_hour=arrival_rate_per_hour,
        max_units=max_units
    )


def compare_scenarios(
    base_config: ProductionLineConfig,
    scenarios: List[Dict[str, Any]],
    duration_hours: float = 8.0,
    random_seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Compare multiple production scenarios.

    Args:
        base_config: Base production line configuration
        scenarios: List of scenario modifications
        duration_hours: Simulation duration
        random_seed: Random seed for reproducibility

    Returns:
        List of comparison results
    """
    results = []

    # Run base scenario
    base_result = run_production_simulation(
        base_config,
        duration_hours=duration_hours,
        random_seed=random_seed
    )

    base_comparison = {
        "scenario": "baseline",
        "config_changes": {},
        "throughput_per_hour": base_result.throughput_per_hour,
        "efficiency": base_result.efficiency,
        "quality_yield": base_result.quality_yield,
        "units_completed": base_result.units_completed,
        "bottleneck": base_result.bottleneck_station,
        "change_from_baseline": {
            "throughput": 0,
            "efficiency": 0,
            "quality": 0
        }
    }
    results.append(base_comparison)

    # Run each scenario
    for i, scenario in enumerate(scenarios):
        # Create modified config
        modified_config = ProductionLineConfig(
            line_id=f"{base_config.line_id}-scenario-{i+1}",
            name=scenario.get("name", f"Scenario {i+1}"),
            stations=base_config.stations.copy(),
            shift_duration_hours=scenario.get("shift_duration_hours", base_config.shift_duration_hours),
            break_duration_minutes=scenario.get("break_duration_minutes", base_config.break_duration_minutes),
            breaks_per_shift=scenario.get("breaks_per_shift", base_config.breaks_per_shift),
            workers_per_station=scenario.get("workers_per_station", base_config.workers_per_station),
            floating_pool_size=scenario.get("floating_pool_size", base_config.floating_pool_size)
        )

        # Modify stations if specified
        if "station_modifications" in scenario:
            modified_stations = []
            for station in base_config.stations:
                mods = scenario["station_modifications"].get(station.name, {})
                modified_stations.append(WorkStation(
                    station_id=station.station_id,
                    name=station.name,
                    station_type=station.station_type,
                    cycle_time_minutes=mods.get("cycle_time_minutes", station.cycle_time_minutes),
                    cycle_time_variability=mods.get("cycle_time_variability", station.cycle_time_variability),
                    num_workers=mods.get("num_workers", station.num_workers),
                    quality_rate=mods.get("quality_rate", station.quality_rate),
                    downtime_probability=mods.get("downtime_probability", station.downtime_probability),
                    downtime_duration_minutes=mods.get("downtime_duration_minutes", station.downtime_duration_minutes)
                ))
            modified_config.stations = modified_stations

        result = run_production_simulation(
            modified_config,
            duration_hours=duration_hours,
            random_seed=random_seed
        )

        scenario_comparison = {
            "scenario": scenario.get("name", f"Scenario {i+1}"),
            "config_changes": scenario,
            "throughput_per_hour": result.throughput_per_hour,
            "efficiency": result.efficiency,
            "quality_yield": result.quality_yield,
            "units_completed": result.units_completed,
            "bottleneck": result.bottleneck_station,
            "change_from_baseline": {
                "throughput": ((result.throughput_per_hour - base_result.throughput_per_hour) /
                              base_result.throughput_per_hour * 100) if base_result.throughput_per_hour > 0 else 0,
                "efficiency": result.efficiency - base_result.efficiency,
                "quality": result.quality_yield - base_result.quality_yield
            }
        }
        results.append(scenario_comparison)

    return results


def analyze_bottlenecks(
    config: ProductionLineConfig,
    duration_hours: float = 8.0,
    random_seed: int = 42
) -> BottleneckAnalysis:
    """
    Analyze bottlenecks in the production line.

    Args:
        config: Production line configuration
        duration_hours: Simulation duration for analysis
        random_seed: Random seed

    Returns:
        BottleneckAnalysis with detailed findings
    """
    simulation = ProductionLineSimulation(config, random_seed=random_seed)
    result = simulation.run(duration_hours=duration_hours)

    # Calculate queue times
    queue_times = {}
    wait_times = {}
    for station_name, waits in simulation.station_waits.items():
        queue_times[station_name] = sum(waits) if waits else 0
        wait_times[station_name] = statistics.mean(waits) if waits else 0

    # Find primary bottleneck
    primary_bottleneck = result.bottleneck_station or "None"
    bottleneck_util = result.utilization_by_station.get(primary_bottleneck, 0)

    # Generate suggestions
    suggestions = []

    if bottleneck_util > 90:
        suggestions.append(f"Critical bottleneck: {primary_bottleneck} at {bottleneck_util:.1f}% utilization")
        suggestions.append("Immediate actions: Add workers, reduce cycle time, or add parallel equipment")
    elif bottleneck_util > 80:
        suggestions.append(f"Moderate bottleneck: {primary_bottleneck} at {bottleneck_util:.1f}% utilization")
        suggestions.append("Consider: Process optimization or additional capacity")

    # Check for secondary bottlenecks
    for station, util in result.utilization_by_station.items():
        if station != primary_bottleneck and util > 75:
            suggestions.append(f"Secondary bottleneck potential: {station} ({util:.1f}%)")

    # Check queue times
    for station, avg_wait in wait_times.items():
        if avg_wait > 10:
            suggestions.append(f"High queue time at {station}: {avg_wait:.1f} min average")

    return BottleneckAnalysis(
        primary_bottleneck=primary_bottleneck,
        bottleneck_utilization=bottleneck_util,
        queue_times=queue_times,
        station_wait_times=wait_times,
        suggestions=suggestions
    )


def simulate_floating_pool_impact(
    config: ProductionLineConfig,
    pool_sizes: List[int],
    duration_hours: float = 8.0,
    random_seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Simulate impact of different floating pool sizes.

    Args:
        config: Base production line configuration
        pool_sizes: List of floating pool sizes to simulate
        duration_hours: Simulation duration
        random_seed: Random seed

    Returns:
        List of results for each pool size
    """
    results = []

    for pool_size in pool_sizes:
        modified_config = ProductionLineConfig(
            line_id=config.line_id,
            name=config.name,
            stations=config.stations,
            shift_duration_hours=config.shift_duration_hours,
            break_duration_minutes=config.break_duration_minutes,
            breaks_per_shift=config.breaks_per_shift,
            workers_per_station=config.workers_per_station,
            floating_pool_size=pool_size
        )

        result = run_production_simulation(
            modified_config,
            duration_hours=duration_hours,
            random_seed=random_seed
        )

        results.append({
            "floating_pool_size": pool_size,
            "throughput_per_hour": result.throughput_per_hour,
            "efficiency": result.efficiency,
            "units_completed": result.units_completed,
            "bottleneck": result.bottleneck_station,
            "quality_yield": result.quality_yield
        })

    return results
