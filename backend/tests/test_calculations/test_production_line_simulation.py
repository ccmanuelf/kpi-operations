"""
Tests for the Production Line Simulation using SimPy
Tests cover: discrete-event simulation, bottleneck analysis, floating pool impact,
scenario comparison, and work station modeling.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from backend.calculations.production_line_simulation import (
    # Enums
    WorkStationType,
    SimulationEvent,
    # Dataclasses
    WorkStation,
    ProductionLineConfig,
    SimulationResult,
    BottleneckAnalysis,
    # Class
    ProductionLineSimulation,
    # Functions
    create_default_production_line,
    run_production_simulation,
    compare_scenarios,
    analyze_bottlenecks,
    simulate_floating_pool_impact,
)


class TestEnums:
    """Tests for enum types"""

    def test_work_station_types(self):
        """Test WorkStationType enum values"""
        assert WorkStationType.RECEIVING.value == "receiving"
        assert WorkStationType.INSPECTION.value == "inspection"
        assert WorkStationType.ASSEMBLY.value == "assembly"
        assert WorkStationType.TESTING.value == "testing"
        assert WorkStationType.PACKAGING.value == "packaging"
        assert WorkStationType.SHIPPING.value == "shipping"

    def test_simulation_events(self):
        """Test SimulationEvent enum values"""
        assert SimulationEvent.UNIT_START.value == "unit_start"
        assert SimulationEvent.UNIT_COMPLETE.value == "unit_complete"
        assert SimulationEvent.STATION_START.value == "station_start"
        assert SimulationEvent.STATION_COMPLETE.value == "station_complete"
        assert SimulationEvent.WORKER_BREAK.value == "worker_break"
        assert SimulationEvent.DOWNTIME_START.value == "downtime_start"
        assert SimulationEvent.DOWNTIME_END.value == "downtime_end"
        assert SimulationEvent.QUALITY_REJECT.value == "quality_reject"


class TestWorkStation:
    """Tests for WorkStation dataclass"""

    def test_create_work_station(self):
        """Test creating a work station"""
        station = WorkStation(
            station_id=1,
            name="Assembly Station",
            station_type=WorkStationType.ASSEMBLY,
            cycle_time_minutes=15.0,
            num_workers=2,
        )

        assert station.station_id == 1
        assert station.name == "Assembly Station"
        assert station.station_type == WorkStationType.ASSEMBLY
        assert station.cycle_time_minutes == 15.0
        assert station.num_workers == 2

    def test_work_station_defaults(self):
        """Test work station default values"""
        station = WorkStation(station_id=1, name="Test", station_type=WorkStationType.TESTING, cycle_time_minutes=10.0)

        assert station.cycle_time_variability == 0.1
        assert station.num_workers == 1
        assert station.quality_rate == 0.98
        assert station.downtime_probability == 0.02
        assert station.downtime_duration_minutes == 30


class TestProductionLineConfig:
    """Tests for ProductionLineConfig dataclass"""

    def test_create_config(self):
        """Test creating production line configuration"""
        stations = [
            WorkStation(station_id=1, name="Station 1", station_type=WorkStationType.RECEIVING, cycle_time_minutes=10.0)
        ]

        config = ProductionLineConfig(line_id="LINE-001", name="Test Line", stations=stations)

        assert config.line_id == "LINE-001"
        assert config.name == "Test Line"
        assert len(config.stations) == 1
        assert config.shift_duration_hours == 8.0  # default

    def test_config_defaults(self):
        """Test configuration default values"""
        config = ProductionLineConfig(line_id="TEST", name="Test", stations=[])

        assert config.shift_duration_hours == 8.0
        assert config.break_duration_minutes == 30
        assert config.breaks_per_shift == 2
        assert config.workers_per_station == 1
        assert config.floating_pool_size == 0


class TestCreateDefaultProductionLine:
    """Tests for create_default_production_line function"""

    def test_create_default_line(self):
        """Test creating default production line"""
        config = create_default_production_line(line_id="TEST-001", num_stations=4, workers_per_station=2)

        assert config.line_id == "TEST-001"
        assert len(config.stations) == 4
        assert config.workers_per_station == 2

    def test_default_line_stations(self):
        """Test default line has correctly configured stations"""
        config = create_default_production_line(num_stations=4)

        # Should have 4 stations
        assert len(config.stations) == 4

        # Each station should have valid configuration
        for station in config.stations:
            assert station.cycle_time_minutes > 0
            assert station.quality_rate > 0
            assert station.quality_rate <= 1

    def test_default_line_with_floating_pool(self):
        """Test default line with floating pool"""
        config = create_default_production_line(floating_pool_size=5)

        assert config.floating_pool_size == 5


class TestProductionLineSimulation:
    """Tests for ProductionLineSimulation class"""

    @pytest.fixture
    def simple_config(self):
        """Create a simple configuration for testing"""
        stations = [
            WorkStation(
                station_id=1,
                name="Station 1",
                station_type=WorkStationType.ASSEMBLY,
                cycle_time_minutes=5.0,
                num_workers=2,
                quality_rate=1.0,  # No defects for predictable testing
                downtime_probability=0,  # No downtime
            ),
            WorkStation(
                station_id=2,
                name="Station 2",
                station_type=WorkStationType.TESTING,
                cycle_time_minutes=5.0,
                num_workers=2,
                quality_rate=1.0,
                downtime_probability=0,
            ),
        ]

        return ProductionLineConfig(line_id="TEST", name="Test Line", stations=stations, floating_pool_size=0)

    def test_simulation_initialization(self, simple_config):
        """Test simulation initializes correctly"""
        sim = ProductionLineSimulation(simple_config, random_seed=42)

        assert sim.config == simple_config
        assert sim.units_started == 0
        assert sim.units_completed == 0
        assert sim.units_rejected == 0

    def test_run_basic_simulation(self, simple_config):
        """Test running a basic simulation"""
        sim = ProductionLineSimulation(simple_config, random_seed=42)
        result = sim.run(duration_hours=1.0, max_units=20)

        assert isinstance(result, SimulationResult)
        assert result.units_started > 0
        assert result.units_completed > 0
        assert result.simulation_duration_hours == 1.0

    def test_simulation_result_structure(self, simple_config):
        """Test simulation result has all required fields"""
        sim = ProductionLineSimulation(simple_config, random_seed=42)
        result = sim.run(duration_hours=0.5, max_units=10)

        # Check all fields exist
        assert result.line_id is not None
        assert result.simulation_duration_hours >= 0
        assert result.units_started >= 0
        assert result.units_completed >= 0
        assert result.units_rejected >= 0
        assert isinstance(result.throughput_per_hour, float)
        assert isinstance(result.utilization_by_station, dict)

    def test_simulation_event_logging(self, simple_config):
        """Test that events are logged during simulation"""
        sim = ProductionLineSimulation(simple_config, random_seed=42)
        result = sim.run(duration_hours=0.5, max_units=5)

        # Should have logged events
        assert len(result.events_log) > 0

        # Check event structure
        event = result.events_log[0]
        assert "time" in event
        assert "event_type" in event

    def test_simulation_with_seed_reproducibility(self, simple_config):
        """Test that same seed produces same results"""
        sim1 = ProductionLineSimulation(simple_config, random_seed=42)
        result1 = sim1.run(duration_hours=0.5, max_units=10)

        sim2 = ProductionLineSimulation(simple_config, random_seed=42)
        result2 = sim2.run(duration_hours=0.5, max_units=10)

        assert result1.units_completed == result2.units_completed


class TestRunProductionSimulation:
    """Tests for run_production_simulation function"""

    def test_basic_simulation_run(self):
        """Test running simulation through high-level function"""
        config = create_default_production_line(num_stations=2)
        result = run_production_simulation(config, duration_hours=1.0, max_units=20, random_seed=42)

        assert isinstance(result, SimulationResult)
        assert result.units_started > 0

    def test_simulation_throughput(self):
        """Test simulation calculates throughput"""
        config = create_default_production_line(num_stations=2, workers_per_station=4)
        result = run_production_simulation(config, duration_hours=2.0, random_seed=42)

        # Throughput should be positive
        assert result.throughput_per_hour >= 0

    def test_simulation_quality_yield(self):
        """Test simulation calculates quality yield"""
        config = create_default_production_line(num_stations=3)
        result = run_production_simulation(config, duration_hours=2.0, random_seed=42)

        # Quality yield should be between 0 and 100
        assert 0 <= result.quality_yield <= 100


class TestCompareScenarios:
    """Tests for compare_scenarios function"""

    def test_baseline_comparison(self):
        """Test that baseline is included in comparison"""
        config = create_default_production_line(num_stations=2)
        scenarios = []

        results = compare_scenarios(config, scenarios, duration_hours=0.5, random_seed=42)

        assert len(results) == 1
        assert results[0]["scenario"] == "baseline"

    def test_scenario_comparison(self):
        """Test comparing multiple scenarios"""
        config = create_default_production_line(num_stations=2, workers_per_station=2)

        scenarios = [{"name": "More Workers", "workers_per_station": 4}, {"name": "With Pool", "floating_pool_size": 3}]

        results = compare_scenarios(config, scenarios, duration_hours=0.5, random_seed=42)

        assert len(results) == 3  # baseline + 2 scenarios
        assert results[0]["scenario"] == "baseline"
        assert results[1]["scenario"] == "More Workers"
        assert results[2]["scenario"] == "With Pool"

    def test_comparison_change_from_baseline(self):
        """Test that change from baseline is calculated"""
        config = create_default_production_line(num_stations=2)

        scenarios = [{"name": "Modified", "workers_per_station": 4}]

        results = compare_scenarios(config, scenarios, duration_hours=1.0, random_seed=42)

        # Should have change_from_baseline for scenario
        assert "change_from_baseline" in results[1]
        assert "throughput" in results[1]["change_from_baseline"]


class TestAnalyzeBottlenecks:
    """Tests for analyze_bottlenecks function"""

    def test_basic_bottleneck_analysis(self):
        """Test basic bottleneck analysis"""
        config = create_default_production_line(num_stations=3)
        analysis = analyze_bottlenecks(config, duration_hours=1.0, random_seed=42)

        assert isinstance(analysis, BottleneckAnalysis)
        assert analysis.primary_bottleneck is not None
        assert isinstance(analysis.queue_times, dict)
        assert isinstance(analysis.station_wait_times, dict)

    def test_bottleneck_utilization(self):
        """Test bottleneck utilization is calculated"""
        # Create config with one slow station (bottleneck)
        stations = [
            WorkStation(
                station_id=1,
                name="Fast Station",
                station_type=WorkStationType.ASSEMBLY,
                cycle_time_minutes=5.0,
                num_workers=2,
            ),
            WorkStation(
                station_id=2,
                name="Slow Station",
                station_type=WorkStationType.TESTING,
                cycle_time_minutes=15.0,  # Much slower
                num_workers=1,
            ),
        ]

        config = ProductionLineConfig(line_id="BOTTLENECK-TEST", name="Bottleneck Test", stations=stations)

        analysis = analyze_bottlenecks(config, duration_hours=1.0, random_seed=42)

        # Slow station should likely be the bottleneck
        assert analysis.bottleneck_utilization >= 0

    def test_bottleneck_suggestions(self):
        """Test bottleneck analysis generates suggestions"""
        config = create_default_production_line(num_stations=3)
        analysis = analyze_bottlenecks(config, duration_hours=2.0, random_seed=42)

        # Should have suggestions list
        assert isinstance(analysis.suggestions, list)


class TestSimulateFloatingPoolImpact:
    """Tests for simulate_floating_pool_impact function"""

    def test_pool_impact_simulation(self):
        """Test simulating floating pool impact"""
        config = create_default_production_line(num_stations=3)
        pool_sizes = [0, 2, 5]

        results = simulate_floating_pool_impact(config, pool_sizes=pool_sizes, duration_hours=1.0, random_seed=42)

        assert len(results) == 3
        for result in results:
            assert "floating_pool_size" in result
            assert "throughput_per_hour" in result
            assert "efficiency" in result

    def test_pool_sizes_in_results(self):
        """Test that all pool sizes are represented in results"""
        config = create_default_production_line(num_stations=2)
        pool_sizes = [0, 3, 6]

        results = simulate_floating_pool_impact(config, pool_sizes=pool_sizes, duration_hours=0.5, random_seed=42)

        result_sizes = [r["floating_pool_size"] for r in results]
        assert result_sizes == [0, 3, 6]


class TestSimulationWithQualityDefects:
    """Tests for simulation with quality defects enabled"""

    @pytest.fixture
    def config_with_quality_issues(self):
        """Create configuration with quality issues"""
        stations = [
            WorkStation(
                station_id=1,
                name="High Quality",
                station_type=WorkStationType.ASSEMBLY,
                cycle_time_minutes=5.0,
                quality_rate=0.99,  # 99% pass rate
            ),
            WorkStation(
                station_id=2,
                name="Low Quality",
                station_type=WorkStationType.TESTING,
                cycle_time_minutes=5.0,
                quality_rate=0.80,  # 80% pass rate - will cause rejects
            ),
        ]

        return ProductionLineConfig(line_id="QUALITY-TEST", name="Quality Test", stations=stations)

    def test_quality_rejects_tracked(self, config_with_quality_issues):
        """Test that quality rejects are tracked"""
        result = run_production_simulation(config_with_quality_issues, duration_hours=1.0, max_units=50, random_seed=42)

        # With 80% quality on one station, should have rejects
        assert result.units_rejected > 0

    def test_quality_yield_calculated(self, config_with_quality_issues):
        """Test quality yield is properly calculated"""
        result = run_production_simulation(config_with_quality_issues, duration_hours=1.0, max_units=50, random_seed=42)

        # Quality yield = completed / (completed + rejected) * 100
        total = result.units_completed + result.units_rejected
        if total > 0:
            expected_yield = result.units_completed / total * 100
            assert abs(result.quality_yield - expected_yield) < 0.1


class TestSimulationResult:
    """Tests for SimulationResult dataclass"""

    def test_result_recommendations(self):
        """Test that simulation generates recommendations"""
        config = create_default_production_line(num_stations=3)
        result = run_production_simulation(config, duration_hours=2.0, random_seed=42)

        # Should have recommendations list
        assert isinstance(result.recommendations, list)

    def test_result_utilization_by_station(self):
        """Test utilization is calculated per station"""
        config = create_default_production_line(num_stations=3)
        result = run_production_simulation(config, duration_hours=1.0, random_seed=42)

        # Should have utilization for each station
        assert len(result.utilization_by_station) == 3

        # Utilization should be between 0 and 100+
        for station, util in result.utilization_by_station.items():
            assert util >= 0


class TestEdgeCases:
    """Tests for edge cases"""

    def test_very_short_duration_simulation(self):
        """Test simulation with very short duration"""
        config = create_default_production_line(num_stations=2)
        result = run_production_simulation(
            config, duration_hours=0.01, random_seed=42  # Very short, not zero (SimPy doesn't allow 0)
        )

        # Very short duration should produce few or no units
        assert result.simulation_duration_hours == 0.01

    def test_single_station_line(self):
        """Test production line with single station"""
        station = WorkStation(
            station_id=1, name="Only Station", station_type=WorkStationType.ASSEMBLY, cycle_time_minutes=10.0
        )

        config = ProductionLineConfig(line_id="SINGLE", name="Single Station", stations=[station])

        result = run_production_simulation(config, duration_hours=0.5, max_units=5, random_seed=42)

        assert result.units_started > 0

    def test_high_arrival_rate(self):
        """Test simulation with high arrival rate"""
        config = create_default_production_line(num_stations=2)
        result = run_production_simulation(
            config, duration_hours=0.5, arrival_rate_per_hour=100, random_seed=42  # High rate
        )

        # Should handle high arrival rate without crashing
        assert isinstance(result, SimulationResult)

    def test_empty_stations_list(self):
        """Test handling of empty stations list raises error due to no capacity"""
        config = ProductionLineConfig(line_id="EMPTY", name="Empty Line", stations=[])

        # Empty stations list causes division by zero when calculating arrival rate
        # This is expected behavior - you can't run a production line without stations
        sim = ProductionLineSimulation(config, random_seed=42)

        with pytest.raises(ZeroDivisionError):
            sim.run(duration_hours=0.5, max_units=5)


class TestIntegration:
    """Integration tests for complete simulation workflows"""

    def test_complete_workflow(self):
        """Test complete simulation workflow"""
        # 1. Create configuration
        config = create_default_production_line(
            line_id="INT-001", num_stations=4, workers_per_station=2, floating_pool_size=2
        )

        # 2. Run simulation
        result = run_production_simulation(config, duration_hours=2.0, random_seed=42)

        # 3. Analyze bottlenecks
        bottleneck_analysis = analyze_bottlenecks(config, duration_hours=2.0, random_seed=42)

        # 4. Compare scenarios
        scenarios = [{"name": "More Workers", "workers_per_station": 4}]
        comparison = compare_scenarios(config, scenarios, duration_hours=1.0, random_seed=42)

        # 5. Analyze floating pool impact
        pool_impact = simulate_floating_pool_impact(config, pool_sizes=[0, 2, 4], duration_hours=1.0, random_seed=42)

        # Verify all steps produced results
        assert result.units_completed > 0
        assert bottleneck_analysis.primary_bottleneck is not None
        assert len(comparison) == 2
        assert len(pool_impact) == 3
