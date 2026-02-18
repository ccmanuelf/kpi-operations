"""
Simulation API — SimPy Production Line Simulation Endpoints

GET  /api/simulation/production-line/guide              — guide for using production line simulation
GET  /api/simulation/production-line/default            — generate default production line config
POST /api/simulation/production-line/run                — run production line simulation
POST /api/simulation/production-line/compare            — compare multiple production scenarios
POST /api/simulation/production-line/bottlenecks        — analyze production line bottlenecks
POST /api/simulation/production-line/floating-pool-impact — analyze floating pool size impact
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.calculations.production_line_simulation import (
    ProductionLineConfig,
    WorkStation,
    WorkStationType,
    run_production_simulation,
    compare_scenarios,
    analyze_bottlenecks,
    simulate_floating_pool_impact,
    create_default_production_line,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

production_line_router = APIRouter()


@production_line_router.get("/production-line/guide")
async def get_production_line_simulation_guide(current_user: User = Depends(get_current_user)) -> dict:
    """
    Get a guide for using the production line simulation.

    Returns configuration options, example scenarios, and best practices.
    """
    return {
        "title": "Production Line Simulation Guide",
        "description": "SimPy-based discrete-event simulation for manufacturing process modeling",
        "quick_start": [
            "1. Use /production-line/default to generate a default production line config",
            "2. Customize the configuration for your specific use case",
            "3. Run simulation with /production-line/run endpoint",
            "4. Analyze bottlenecks with /production-line/bottlenecks",
            "5. Compare scenarios with /production-line/compare",
        ],
        "configuration_options": {
            "line_config": {
                "line_id": "Unique identifier for the production line",
                "name": "Human-readable name",
                "shift_duration_hours": "Length of a shift (default: 8)",
                "break_duration_minutes": "Duration of breaks (default: 30)",
                "breaks_per_shift": "Number of breaks per shift (default: 2)",
                "workers_per_station": "Default workers per station",
                "floating_pool_size": "Number of floating pool workers",
            },
            "station_config": {
                "station_id": "Unique station identifier",
                "name": "Station name",
                "station_type": ["receiving", "inspection", "assembly", "testing", "packaging", "shipping"],
                "cycle_time_minutes": "Average processing time per unit",
                "cycle_time_variability": "Variability coefficient (0.1 = 10% variation)",
                "num_workers": "Workers assigned to this station",
                "quality_rate": "Pass rate (0.98 = 98% pass)",
                "downtime_probability": "Hourly downtime probability (0.02 = 2%)",
                "downtime_duration_minutes": "Average downtime duration",
            },
        },
        "example_scenarios": [
            {
                "name": "Add Workers to Bottleneck",
                "description": "Increase workers at the slowest station",
                "config_change": {"workers_per_station": 3},
            },
            {
                "name": "Reduce Cycle Time",
                "description": "Improve process to reduce cycle time by 20%",
                "station_modifications": {"Assembly 2": {"cycle_time_minutes": 12}},
            },
            {
                "name": "Add Floating Pool",
                "description": "Add flexible workers to cover gaps",
                "config_change": {"floating_pool_size": 2},
            },
        ],
        "best_practices": [
            "Start with the default configuration and adjust based on your actual data",
            "Run simulations for at least 8 hours (one shift) for meaningful results",
            "Use random_seed for reproducible results when comparing scenarios",
            "Focus on bottleneck stations first - they limit overall throughput",
            "Consider quality rates and downtime, not just cycle times",
        ],
        "metrics_explained": {
            "throughput_per_hour": "Units completed per hour",
            "efficiency": "Actual vs theoretical output percentage",
            "utilization": "Time station is busy vs available",
            "bottleneck": "Station with highest utilization limiting throughput",
            "quality_yield": "Percentage of units passing all quality checks",
        },
    }


@production_line_router.get("/production-line/default")
async def get_default_production_line_config(
    num_stations: int = Query(default=4, ge=2, le=10, description="Number of work stations"),
    workers_per_station: int = Query(default=2, ge=1, le=10, description="Workers per station"),
    floating_pool_size: int = Query(default=0, ge=0, le=10, description="Floating pool size"),
    base_cycle_time: float = Query(default=15.0, gt=0, le=120, description="Base cycle time in minutes"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Generate a default production line configuration.

    Use this as a starting point and customize for your specific needs.
    """
    config = create_default_production_line(
        line_id=f"LINE-{current_user.client_id_assigned or 'DEFAULT'}",
        num_stations=num_stations,
        workers_per_station=workers_per_station,
        floating_pool_size=floating_pool_size,
        base_cycle_time=base_cycle_time,
    )

    return {
        "line_id": config.line_id,
        "name": config.name,
        "shift_duration_hours": config.shift_duration_hours,
        "break_duration_minutes": config.break_duration_minutes,
        "breaks_per_shift": config.breaks_per_shift,
        "workers_per_station": config.workers_per_station,
        "floating_pool_size": config.floating_pool_size,
        "stations": [
            {
                "station_id": s.station_id,
                "name": s.name,
                "station_type": s.station_type.value,
                "cycle_time_minutes": s.cycle_time_minutes,
                "cycle_time_variability": s.cycle_time_variability,
                "num_workers": s.num_workers,
                "quality_rate": s.quality_rate,
                "downtime_probability": s.downtime_probability,
                "downtime_duration_minutes": s.downtime_duration_minutes,
            }
            for s in config.stations
        ],
    }


def _parse_stations(stations_data: list) -> list:
    """Parse station dicts into WorkStation objects."""
    return [
        WorkStation(
            station_id=s["station_id"],
            name=s["name"],
            station_type=WorkStationType(s["station_type"]),
            cycle_time_minutes=s["cycle_time_minutes"],
            cycle_time_variability=s.get("cycle_time_variability", 0.1),
            num_workers=s.get("num_workers", 1),
            quality_rate=s.get("quality_rate", 0.98),
            downtime_probability=s.get("downtime_probability", 0.02),
            downtime_duration_minutes=s.get("downtime_duration_minutes", 30),
        )
        for s in stations_data
    ]


def _build_line_config(config: dict, stations: list) -> ProductionLineConfig:
    """Build a ProductionLineConfig from a config dict and pre-parsed stations."""
    return ProductionLineConfig(
        line_id=config.get("line_id", "LINE-001"),
        name=config.get("name", "Production Line"),
        stations=stations,
        shift_duration_hours=config.get("shift_duration_hours", 8.0),
        break_duration_minutes=config.get("break_duration_minutes", 30),
        breaks_per_shift=config.get("breaks_per_shift", 2),
        workers_per_station=config.get("workers_per_station", 1),
        floating_pool_size=config.get("floating_pool_size", 0),
    )


@production_line_router.post("/production-line/run")
async def run_production_line_simulation(
    config: dict,
    duration_hours: float = Query(default=8.0, gt=0, le=24, description="Simulation duration in hours"),
    arrival_rate_per_hour: Optional[float] = Query(
        default=None, gt=0, description="Unit arrival rate (auto-calculated if not specified)"
    ),
    max_units: Optional[int] = Query(default=None, gt=0, description="Maximum units to simulate"),
    random_seed: int = Query(default=42, description="Random seed for reproducibility"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Run a production line simulation with custom configuration.

    Args:
        config: Production line configuration (use /production-line/default as template)
        duration_hours: How long to simulate (default: 8 hours = one shift)
        arrival_rate_per_hour: How many units arrive per hour (auto-calculated if not set)
        max_units: Stop after this many units (optional)
        random_seed: For reproducible results

    Returns:
        Complete simulation results with metrics and recommendations
    """
    try:
        stations = _parse_stations(config["stations"])
        line_config = _build_line_config(config, stations)

        result = run_production_simulation(
            config=line_config,
            duration_hours=duration_hours,
            arrival_rate_per_hour=arrival_rate_per_hour,
            max_units=max_units,
            random_seed=random_seed,
        )

        return {
            "line_id": result.line_id,
            "simulation_duration_hours": result.simulation_duration_hours,
            "summary": {
                "units_started": result.units_started,
                "units_completed": result.units_completed,
                "units_rejected": result.units_rejected,
                "throughput_per_hour": round(result.throughput_per_hour, 2),
                "efficiency": round(result.efficiency, 2),
                "quality_yield": round(result.quality_yield, 2),
                "total_downtime_minutes": round(result.total_downtime_minutes, 2),
            },
            "bottleneck_analysis": {
                "bottleneck_station": result.bottleneck_station,
                "avg_cycle_time_minutes": round(result.avg_cycle_time_minutes, 2),
            },
            "station_utilization": {k: round(v, 2) for k, v in result.utilization_by_station.items()},
            "recommendations": result.recommendations,
            "events_sample": result.events_log[:20] if result.events_log else [],
        }

    except Exception as e:
        logger.exception("Failed to run production line simulation: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed. Check server logs for details.")


@production_line_router.post("/production-line/compare")
async def compare_production_scenarios(
    base_config: dict,
    scenarios: List[dict],
    duration_hours: float = Query(default=8.0, gt=0, le=24),
    random_seed: int = Query(default=42),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Compare multiple production scenarios against a baseline.

    Args:
        base_config: Base production line configuration
        scenarios: List of scenario modifications to compare
        duration_hours: Simulation duration
        random_seed: For reproducible comparisons

    Returns:
        Comparison results showing impact of each scenario
    """
    try:
        base_stations = _parse_stations(base_config["stations"])
        line_config = _build_line_config(base_config, base_stations)

        results = compare_scenarios(
            base_config=line_config, scenarios=scenarios, duration_hours=duration_hours, random_seed=random_seed
        )

        return {
            "comparison_date": datetime.now(tz=timezone.utc).isoformat(),
            "duration_hours": duration_hours,
            "baseline": results[0] if results else None,
            "scenarios": results[1:] if len(results) > 1 else [],
            "summary": {
                "best_throughput": max(r["throughput_per_hour"] for r in results) if results else 0,
                "best_scenario": max(results, key=lambda r: r["throughput_per_hour"])["scenario"] if results else None,
                "highest_efficiency": max(r["efficiency"] for r in results) if results else 0,
            },
        }

    except Exception as e:
        logger.exception("Failed to compare production scenarios: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed. Check server logs for details.")


@production_line_router.post("/production-line/bottlenecks")
async def analyze_production_bottlenecks(
    config: dict,
    duration_hours: float = Query(default=8.0, gt=0, le=24),
    random_seed: int = Query(default=42),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Analyze bottlenecks in the production line.

    Returns detailed analysis of where constraints are limiting throughput.
    """
    try:
        stations = _parse_stations(config["stations"])
        line_config = _build_line_config(config, stations)

        analysis = analyze_bottlenecks(config=line_config, duration_hours=duration_hours, random_seed=random_seed)

        return {
            "primary_bottleneck": analysis.primary_bottleneck,
            "bottleneck_utilization": round(analysis.bottleneck_utilization, 2),
            "queue_times": {k: round(v, 2) for k, v in analysis.queue_times.items()},
            "station_wait_times": {k: round(v, 2) for k, v in analysis.station_wait_times.items()},
            "suggestions": analysis.suggestions,
        }

    except Exception as e:
        logger.exception("Failed to analyze production bottlenecks: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed. Check server logs for details.")


@production_line_router.post("/production-line/floating-pool-impact")
async def analyze_floating_pool_impact(
    config: dict,
    pool_sizes: List[int] = Query(default=[0, 1, 2, 3, 5], description="Pool sizes to simulate"),
    duration_hours: float = Query(default=8.0, gt=0, le=24),
    random_seed: int = Query(default=42),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Analyze the impact of different floating pool sizes on production.

    Compares throughput, efficiency, and quality across different pool sizes.
    """
    try:
        stations = _parse_stations(config["stations"])
        # floating_pool_size will be varied by simulate_floating_pool_impact
        config_with_zero_pool = dict(config)
        config_with_zero_pool["floating_pool_size"] = 0
        line_config = _build_line_config(config_with_zero_pool, stations)

        results = simulate_floating_pool_impact(
            config=line_config, pool_sizes=pool_sizes, duration_hours=duration_hours, random_seed=random_seed
        )

        # Calculate optimal pool size
        optimal = max(results, key=lambda r: r["throughput_per_hour"]) if results else None

        return {
            "pool_size_comparison": results,
            "optimal_pool_size": optimal["floating_pool_size"] if optimal else 0,
            "optimal_throughput": optimal["throughput_per_hour"] if optimal else 0,
            "recommendations": [
                f"Optimal floating pool size is {optimal['floating_pool_size']} workers" if optimal else "No data",
                f"This provides throughput of {optimal['throughput_per_hour']:.1f} units/hour" if optimal else "",
            ],
        }

    except Exception as e:
        logger.exception("Failed to analyze floating pool impact: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed. Check server logs for details.")
