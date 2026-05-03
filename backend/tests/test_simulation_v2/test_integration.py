"""
Integration tests for Production Line Simulation v2.0

Tests the complete simulation workflow from API request to response.
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth.jwt import get_current_user
from backend.simulation_v2.models import (
    SimulationConfig,
    SimulationRequest,
    ScheduleConfig,
    OperationInput,
    DemandInput,
    DemandMode,
)


def get_mock_admin_user():
    """Create a mock admin user."""
    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.username = "test_admin"
    mock_user.id = 1
    return mock_user


def get_mock_operator_user():
    """Create a mock operator user with insufficient permissions."""
    mock_user = MagicMock()
    mock_user.role = "operator"
    mock_user.username = "test_operator"
    mock_user.id = 2
    return mock_user


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_client():
    """Create test client with admin authentication."""
    app.dependency_overrides[get_current_user] = get_mock_admin_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def operator_client():
    """Create test client with operator authentication."""
    app.dependency_overrides[get_current_user] = get_mock_operator_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def valid_config_payload():
    """Create a valid simulation configuration payload."""
    return {
        "config": {
            "operations": [
                {
                    "product": "T_SHIRT_A",
                    "step": 1,
                    "operation": "Cut fabric panels",
                    "machine_tool": "Cutting Table",
                    "sam_min": 2.0,
                    "sequence": "Cutting",
                    "grouping": "PREP",
                    "operators": 2,
                    "variability": "triangular",
                    "rework_pct": 0,
                    "grade_pct": 85,
                    "fpd_pct": 15,
                },
                {
                    "product": "T_SHIRT_A",
                    "step": 2,
                    "operation": "Sew shoulder seams",
                    "machine_tool": "Overlock 4-thread",
                    "sam_min": 3.5,
                    "sequence": "Assembly",
                    "grouping": "SEW",
                    "operators": 3,
                    "variability": "triangular",
                    "rework_pct": 2,
                    "grade_pct": 90,
                    "fpd_pct": 15,
                },
                {
                    "product": "T_SHIRT_A",
                    "step": 3,
                    "operation": "Final inspection",
                    "machine_tool": "QC Station",
                    "sam_min": 1.0,
                    "sequence": "Finishing",
                    "grouping": "QC",
                    "operators": 1,
                    "variability": "deterministic",
                    "rework_pct": 0,
                    "grade_pct": 100,
                    "fpd_pct": 10,
                },
            ],
            "schedule": {
                "shifts_enabled": 1,
                "shift1_hours": 8.0,
                "shift2_hours": 0.0,
                "shift3_hours": 0.0,
                "work_days": 5,
                "ot_enabled": False,
            },
            "demands": [{"product": "T_SHIRT_A", "bundle_size": 10, "daily_demand": 200, "weekly_demand": 1000}],
            "mode": "demand-driven",
            "horizon_days": 1,
        }
    }


@pytest.fixture
def invalid_config_payload():
    """Create an invalid simulation configuration payload."""
    return {
        "config": {
            "operations": [
                {
                    "product": "T_SHIRT_A",
                    "step": 1,
                    "operation": "Cut fabric panels",
                    "machine_tool": "Cutting Table",
                    "sam_min": 2.0,
                },
                {
                    "product": "T_SHIRT_A",
                    "step": 3,  # Gap - step 2 is missing!
                    "operation": "Final inspection",
                    "machine_tool": "QC Station",
                    "sam_min": 1.0,
                },
            ],
            "schedule": {"shifts_enabled": 1, "shift1_hours": 8.0, "work_days": 5},
            "demands": [{"product": "T_SHIRT_A", "bundle_size": 10, "daily_demand": 200}],
            "mode": "demand-driven",
            "horizon_days": 1,
        }
    }


class TestSimulationInfoEndpoint:
    """Test the simulation info endpoint."""

    def test_info_endpoint_accessible_without_auth(self, client):
        """Test that info endpoint is publicly accessible."""
        response = client.get("/api/v2/simulation/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Production Line Simulation Tool"
        assert data["version"] == "2.0.0"
        assert "capabilities" in data
        assert "limitations" in data
        assert "constraints" in data

    def test_info_returns_constraints(self, client):
        """Test that info endpoint returns configuration constraints."""
        response = client.get("/api/v2/simulation/")

        data = response.json()
        constraints = data["constraints"]
        assert constraints["max_products"] == 5
        assert constraints["max_operations_per_product"] == 50


class TestValidationEndpoint:
    """Test the validation endpoint."""

    def test_validate_requires_auth(self, client, valid_config_payload):
        """Test that validation endpoint requires authentication."""
        response = client.post("/api/v2/simulation/validate", json=valid_config_payload)

        assert response.status_code == 401

    def test_validate_valid_config(self, admin_client, valid_config_payload):
        """Test validation of a valid configuration."""
        response = admin_client.post("/api/v2/simulation/validate", json=valid_config_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert len(data["errors"]) == 0

    def test_validate_invalid_config_returns_errors(self, admin_client, invalid_config_payload):
        """Test validation of invalid configuration returns errors."""
        response = admin_client.post("/api/v2/simulation/validate", json=invalid_config_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0
        # Should detect the gap in steps
        assert any("gap" in e["message"].lower() for e in data["errors"])


class TestRunSimulationEndpoint:
    """Test the run simulation endpoint."""

    def test_run_requires_auth(self, client, valid_config_payload):
        """Test that run endpoint requires authentication."""
        response = client.post("/api/v2/simulation/run", json=valid_config_payload)

        assert response.status_code == 401

    def test_run_requires_sufficient_role(self, operator_client, valid_config_payload):
        """Test that run endpoint requires appropriate role."""
        response = operator_client.post("/api/v2/simulation/run", json=valid_config_payload)

        assert response.status_code == 403

    def test_run_valid_simulation(self, admin_client, valid_config_payload):
        """Test running a valid simulation."""
        response = admin_client.post("/api/v2/simulation/run", json=valid_config_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["results"] is not None

        # Check all 8 blocks are present
        results = data["results"]
        assert "weekly_demand_capacity" in results
        assert "daily_summary" in results
        assert "station_performance" in results
        assert "free_capacity" in results
        assert "bundle_metrics" in results
        assert "per_product_summary" in results
        assert "rebalancing_suggestions" in results
        assert "assumption_log" in results

    def test_run_invalid_config_returns_validation_errors(self, admin_client, invalid_config_payload):
        """Test that invalid config returns validation errors without running."""
        response = admin_client.post("/api/v2/simulation/run", json=invalid_config_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["results"] is None
        assert len(data["validation_report"]["errors"]) > 0


class TestSimulationOutputBlocks:
    """Test the structure and content of simulation output blocks."""

    @pytest.fixture
    def run_simulation(self, admin_client, valid_config_payload):
        """Run a simulation and return results."""
        response = admin_client.post("/api/v2/simulation/run", json=valid_config_payload)
        return response.json()["results"]

    def test_block1_weekly_demand_capacity(self, run_simulation):
        """Test Block 1: Weekly Demand vs Capacity."""
        block = run_simulation["weekly_demand_capacity"]

        assert len(block) == 1
        row = block[0]
        assert row["product"] == "T_SHIRT_A"
        assert row["weekly_demand_pcs"] == 1000
        assert "max_weekly_capacity_pcs" in row
        assert "demand_coverage_pct" in row
        assert row["status"] in ["OK", "Tight", "Shortfall"]

    def test_block2_daily_summary(self, run_simulation):
        """Test Block 2: Daily Summary."""
        block = run_simulation["daily_summary"]

        assert block["total_shifts_per_day"] == 1
        assert block["daily_planned_hours"] == 8.0
        assert block["daily_demand_pcs"] == 200
        assert "daily_throughput_pcs" in block
        assert "daily_coverage_pct" in block
        assert "avg_cycle_time_min" in block
        assert "avg_wip_pcs" in block

    def test_block3_station_performance(self, run_simulation):
        """Test Block 3: Station Performance."""
        block = run_simulation["station_performance"]

        assert len(block) == 3  # 3 operations
        for row in block:
            assert "product" in row
            assert "step" in row
            assert "operation" in row
            assert "machine_tool" in row
            assert "util_pct" in row
            assert "is_bottleneck" in row
            assert "is_donor" in row

    def test_block4_free_capacity(self, run_simulation):
        """Test Block 4: Free Capacity Analysis."""
        block = run_simulation["free_capacity"]

        assert "daily_demand_pcs" in block
        assert "daily_max_capacity_pcs" in block
        assert "demand_usage_pct" in block
        assert "free_line_hours_per_day" in block

    def test_block5_bundle_metrics(self, run_simulation):
        """Test Block 5: Bundle Metrics."""
        block = run_simulation["bundle_metrics"]

        assert len(block) == 1
        row = block[0]
        assert row["product"] == "T_SHIRT_A"
        assert row["bundle_size_pcs"] == 10
        assert "bundles_arriving_per_day" in row

    def test_block6_per_product_summary(self, run_simulation):
        """Test Block 6: Per-Product Summary."""
        block = run_simulation["per_product_summary"]

        assert len(block) == 1
        row = block[0]
        assert row["product"] == "T_SHIRT_A"
        assert "daily_demand_pcs" in row
        assert "daily_throughput_pcs" in row
        assert "daily_coverage_pct" in row
        assert "weekly_demand_pcs" in row
        assert "weekly_throughput_pcs" in row

    def test_block7_rebalancing_suggestions(self, run_simulation):
        """Test Block 7: Rebalancing Suggestions."""
        block = run_simulation["rebalancing_suggestions"]

        # May be empty if line is balanced
        assert isinstance(block, list)
        for suggestion in block:
            assert "product" in suggestion
            assert "operation" in suggestion
            assert "operators_before" in suggestion
            assert "operators_after" in suggestion
            assert "role" in suggestion

    def test_block8_assumption_log(self, run_simulation):
        """Test Block 8: Assumption Log."""
        block = run_simulation["assumption_log"]

        assert block["simulation_engine_version"] == "2.0.0"
        assert block["configuration_mode"] == "demand-driven"
        assert "schedule" in block
        assert "products" in block
        assert "formula_implementations" in block
        assert "limitations_and_caveats" in block


class TestSchemaEndpoint:
    """Test the schema endpoint."""

    def test_schema_returns_json_schema(self, client):
        """Test that schema endpoint returns valid JSON schema."""
        response = client.get("/api/v2/simulation/schema")

        assert response.status_code == 200
        schema = response.json()
        assert "properties" in schema
        assert "operations" in schema["properties"]
        assert "schedule" in schema["properties"]
        assert "demands" in schema["properties"]


class TestOptimizeOperatorsEndpoint:
    """Test the Pattern-1 operator-allocation endpoint."""

    def test_optimize_requires_auth(self, client, valid_config_payload):
        body = {**valid_config_payload, "max_operators_per_op": 10}
        response = client.post("/api/v2/simulation/optimize-operators", json=body)
        assert response.status_code == 401

    def test_optimize_requires_sufficient_role(self, operator_client, valid_config_payload):
        body = {**valid_config_payload, "max_operators_per_op": 10}
        response = operator_client.post("/api/v2/simulation/optimize-operators", json=body)
        assert response.status_code == 403

    def test_optimize_rejects_max_operators_below_one(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "max_operators_per_op": 0}
        response = admin_client.post("/api/v2/simulation/optimize-operators", json=body)
        assert response.status_code == 422

    def test_optimize_rejects_negative_budget(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "total_operators_budget": -1}
        response = admin_client.post("/api/v2/simulation/optimize-operators", json=body)
        assert response.status_code == 422

    def test_optimize_invalid_config_returns_validation_failure(
        self, admin_client, invalid_config_payload
    ):
        response = admin_client.post(
            "/api/v2/simulation/optimize-operators",
            json={**invalid_config_payload, "max_operators_per_op": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["status"] == "validation-failed"

    def test_optimize_happy_path(self, admin_client, valid_config_payload):
        """Happy path: valid config solves and returns proposals."""
        from backend.simulation_v2.optimization import is_minizinc_available
        if not is_minizinc_available():
            import pytest
            pytest.skip("MiniZinc CLI not available")

        body = {**valid_config_payload, "max_operators_per_op": 10}
        response = admin_client.post("/api/v2/simulation/optimize-operators", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_optimal"] is True
        assert data["total_operators_after"] >= 1
        assert data["total_operators_after"] <= data["total_operators_before"]

        # Each proposal echoes the source operation and includes a prediction.
        assert len(data["proposals"]) == 3
        for prop in data["proposals"]:
            assert prop["product"] == "T_SHIRT_A"
            assert prop["operators_after"] >= 1
            assert prop["predicted_pcs_per_day"] >= prop["demand_pcs_per_day"]

    def test_optimize_with_validation_run(self, admin_client, valid_config_payload):
        """When validate_with_simulation=true, endpoint returns a SimPy run."""
        from backend.simulation_v2.optimization import is_minizinc_available
        if not is_minizinc_available():
            import pytest
            pytest.skip("MiniZinc CLI not available")

        body = {
            **valid_config_payload,
            "max_operators_per_op": 10,
            "validate_with_simulation": True,
        }
        response = admin_client.post("/api/v2/simulation/optimize-operators", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["validation_run"] is not None
        # validation_run is a full SimulationResults shape.
        assert "daily_summary" in data["validation_run"]
        assert "weekly_demand_capacity" in data["validation_run"]


class TestRebalanceBottlenecksEndpoint:
    """Test the Pattern-2 bottleneck-rebalancing endpoint."""

    def test_rebalance_requires_auth(self, client, valid_config_payload):
        body = {**valid_config_payload, "max_operators_per_op": 10}
        response = client.post("/api/v2/simulation/rebalance-bottlenecks", json=body)
        assert response.status_code == 401

    def test_rebalance_requires_sufficient_role(self, operator_client, valid_config_payload):
        body = {**valid_config_payload, "max_operators_per_op": 10}
        response = operator_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 403

    def test_rebalance_rejects_max_per_op_below_one(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "max_operators_per_op": 0}
        response = admin_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 422

    def test_rebalance_rejects_total_delta_max_negative(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "total_delta_max": -1}
        response = admin_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 422

    def test_rebalance_rejects_total_delta_min_positive(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "total_delta_min": 5}
        response = admin_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 422

    def test_rebalance_invalid_config_returns_validation_failure(
        self, admin_client, invalid_config_payload
    ):
        body = {**invalid_config_payload, "max_operators_per_op": 10}
        response = admin_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["status"] == "validation-failed"

    def test_rebalance_happy_path(self, admin_client, valid_config_payload):
        from backend.simulation_v2.optimization import is_minizinc_available
        if not is_minizinc_available():
            import pytest
            pytest.skip("MiniZinc CLI not available")

        body = {**valid_config_payload, "max_operators_per_op": 10}
        response = admin_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_satisfied"] is True
        # Each proposal echoes the source operation and includes delta + slack.
        for prop in data["proposals"]:
            assert "delta" in prop
            assert "slack_pcs" in prop
            assert prop["operators_after"] == prop["operators_before"] + prop["delta"]

    def test_rebalance_with_validation_run(self, admin_client, valid_config_payload):
        from backend.simulation_v2.optimization import is_minizinc_available
        if not is_minizinc_available():
            import pytest
            pytest.skip("MiniZinc CLI not available")

        body = {
            **valid_config_payload,
            "max_operators_per_op": 10,
            "validate_with_simulation": True,
        }
        response = admin_client.post(
            "/api/v2/simulation/rebalance-bottlenecks", json=body
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["validation_run"] is not None
        assert "daily_summary" in data["validation_run"]


class TestRunMonteCarloEndpoint:
    """Test the Monte Carlo simulation endpoint."""

    def test_monte_carlo_requires_auth(self, client, valid_config_payload):
        body = {**valid_config_payload, "n_replications": 3, "base_seed": 1}
        response = client.post("/api/v2/simulation/run-monte-carlo", json=body)
        assert response.status_code == 401

    def test_monte_carlo_requires_sufficient_role(self, operator_client, valid_config_payload):
        body = {**valid_config_payload, "n_replications": 3, "base_seed": 1}
        response = operator_client.post("/api/v2/simulation/run-monte-carlo", json=body)
        assert response.status_code == 403

    def test_monte_carlo_rejects_n_below_two(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "n_replications": 1, "base_seed": 1}
        response = admin_client.post("/api/v2/simulation/run-monte-carlo", json=body)
        # Pydantic catches `ge=2` constraint → 422.
        assert response.status_code == 422

    def test_monte_carlo_rejects_n_above_one_hundred(self, admin_client, valid_config_payload):
        body = {**valid_config_payload, "n_replications": 101, "base_seed": 1}
        response = admin_client.post("/api/v2/simulation/run-monte-carlo", json=body)
        assert response.status_code == 422

    def test_monte_carlo_valid_run_aggregates_blocks(self, admin_client, valid_config_payload):
        """Happy path: 3 replications, deterministic seed, all blocks aggregated."""
        body = {**valid_config_payload, "n_replications": 3, "base_seed": 7}
        response = admin_client.post("/api/v2/simulation/run-monte-carlo", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["n_replications"] == 3
        assert data["base_seed"] == 7
        assert data["total_duration_seconds"] > 0
        assert len(data["per_run_duration_seconds"]) == 3

        # All six numeric blocks aggregated.
        agg = data["aggregated_stats"]
        for block in (
            "daily_summary",
            "free_capacity",
            "weekly_demand_capacity",
            "station_performance",
            "bundle_metrics",
            "per_product_summary",
        ):
            assert block in agg, f"missing aggregated block {block}"

        # daily_summary is a singleton → flat dict; daily_throughput_pcs
        # has stat shape.
        ds = agg["daily_summary"]
        assert "daily_throughput_pcs" in ds
        stat = ds["daily_throughput_pcs"]
        assert {"mean", "std", "ci_lo_95", "ci_hi_95", "n"}.issubset(stat.keys())
        assert stat["n"] == 3
        assert stat["ci_lo_95"] <= stat["mean"] <= stat["ci_hi_95"]

        # sample_run carries non-numeric blocks for inspection.
        assert data["sample_run"] is not None
        assert "rebalancing_suggestions" in data["sample_run"]
        assert "assumption_log" in data["sample_run"]

    def test_monte_carlo_invalid_config_returns_validation_errors(
        self, admin_client, invalid_config_payload
    ):
        body = {**invalid_config_payload, "n_replications": 3, "base_seed": 1}
        response = admin_client.post("/api/v2/simulation/run-monte-carlo", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["sample_run"] is None
        assert data["aggregated_stats"] == {}
        assert len(data["validation_report"]["errors"]) > 0
