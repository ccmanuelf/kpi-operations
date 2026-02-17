"""
Production Line Simulation v2.0 - API Endpoints

Provides REST endpoints for the ephemeral simulation tool.
All endpoints are stateless with no database dependencies.

This is a new v2 implementation that operates as a pure calculator
tool without persisting scenarios to the database.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.jwt import get_current_user
from backend.schemas.user import User

from backend.simulation_v2.models import (
    SimulationConfig,
    SimulationRequest,
    SimulationResponse,
    ValidationReport,
)
from backend.simulation_v2.validation import validate_simulation_config
from backend.simulation_v2.engine import run_simulation
from backend.simulation_v2.calculations import calculate_all_blocks
from backend.simulation_v2.constants import (
    MAX_PRODUCTS,
    MAX_OPERATIONS_PER_PRODUCT,
    MAX_TOTAL_OPERATIONS,
    MAX_HORIZON_DAYS,
    ENGINE_VERSION,
    DEFAULT_GRADE_PCT,
    DEFAULT_FPD_PCT,
    DEFAULT_REWORK_PCT,
    DEFAULT_OPERATORS,
    DEFAULT_SEQUENCE,
    DEFAULT_VARIABILITY,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(
    prefix="/api/v2/simulation",
    tags=["simulation-v2"],
    responses={404: {"description": "Not found"}},
)


# =============================================================================
# Permission Helpers
# =============================================================================


def _check_simulation_permission(user: User) -> None:
    """
    Verify user has permission to run simulations.

    Simulation access is restricted to leadership and admin roles
    to prevent resource-intensive operations by general users.
    """
    allowed_roles = {"admin", "poweruser", "leader", "supervisor"}
    user_role = user.role.lower() if user.role else ""

    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation access requires Leader, PowerUser, Supervisor, or Admin role",
        )


def _track_defaults(config: SimulationConfig) -> list:
    """
    Track which operations used default values.

    This is recorded in the assumption log for audit purposes.
    """
    defaults = []

    for op in config.operations:
        applied = []

        # Check each optional field against known defaults
        if op.sequence == DEFAULT_SEQUENCE:
            applied.append(f"sequence: '{DEFAULT_SEQUENCE}'")
        if op.operators == DEFAULT_OPERATORS:
            applied.append(f"operators: {DEFAULT_OPERATORS}")
        if op.variability.value == DEFAULT_VARIABILITY:
            applied.append(f"variability: '{DEFAULT_VARIABILITY}'")
        if op.rework_pct == DEFAULT_REWORK_PCT:
            applied.append(f"rework_pct: {DEFAULT_REWORK_PCT}")
        if op.grade_pct == DEFAULT_GRADE_PCT:
            applied.append(f"grade_pct: {DEFAULT_GRADE_PCT}")
        if op.fpd_pct == DEFAULT_FPD_PCT:
            applied.append(f"fpd_pct: {DEFAULT_FPD_PCT}")

        if applied:
            defaults.append(
                {"product": op.product, "step": op.step, "operation": op.operation, "defaults_used": applied}
            )

    return defaults


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/")
async def simulation_info():
    """
    Get simulation tool information and capabilities.

    Returns version, capabilities, and limitations of the v2 simulation tool.
    This endpoint is unauthenticated for discoverability.
    """
    return {
        "name": "Production Line Simulation Tool",
        "version": ENGINE_VERSION,
        "description": "Ephemeral capacity planning and line behavior simulation for labor-intensive manufacturing",
        "capabilities": [
            "Multi-product discrete-event simulation (up to 5 products)",
            "SimPy-based process simulation with stochastic variability",
            "Bundle-based workflow with configurable batch sizes",
            "Bottleneck detection and rebalancing suggestions",
            "8 comprehensive output blocks for analysis",
            "Client-side Excel export support",
        ],
        "limitations": [
            "No persistent storage of scenarios (ephemeral only)",
            "No database integration",
            "Single replication per run (no Monte Carlo)",
            "Equipment breakdown model is simplified",
        ],
        "constraints": {
            "max_products": MAX_PRODUCTS,
            "max_operations_per_product": MAX_OPERATIONS_PER_PRODUCT,
            "max_total_operations": MAX_TOTAL_OPERATIONS,
            "max_horizon_days": MAX_HORIZON_DAYS,
        },
        "default_values": {
            "grade_pct": DEFAULT_GRADE_PCT,
            "fpd_pct": DEFAULT_FPD_PCT,
            "rework_pct": DEFAULT_REWORK_PCT,
            "operators": DEFAULT_OPERATORS,
            "variability": DEFAULT_VARIABILITY,
        },
    }


@router.post("/validate", response_model=ValidationReport)
async def validate_configuration(
    request: SimulationRequest, current_user: User = Depends(get_current_user)
) -> ValidationReport:
    """
    Validate simulation configuration without running simulation.

    Use this endpoint to check inputs before committing to a full simulation run.
    Returns errors, warnings, and info messages about the configuration.

    - **Errors**: Must be fixed before simulation can run
    - **Warnings**: Potential issues but won't block simulation
    - **Info**: Informational messages about configuration
    """
    _check_simulation_permission(current_user)

    logger.info(
        f"User {current_user.username} validating simulation config: "
        f"{len(request.config.operations)} operations, {len(request.config.demands)} demands"
    )

    report = validate_simulation_config(request.config)

    logger.info(
        f"Validation complete: {len(report.errors)} errors, "
        f"{len(report.warnings)} warnings, valid={report.is_valid}"
    )

    return report


@router.post("/run", response_model=SimulationResponse)
async def run_simulation_endpoint(
    request: SimulationRequest, current_user: User = Depends(get_current_user)
) -> SimulationResponse:
    """
    Run complete simulation and return results.

    This endpoint:
    1. Validates inputs (returns errors if invalid)
    2. Runs the SimPy discrete-event simulation
    3. Calculates all 8 output blocks
    4. Returns comprehensive results

    Results are NOT stored - use client-side Excel export for persistence.

    **Output Blocks:**
    1. Weekly Demand vs Capacity
    2. Daily Summary
    3. Station/Operation Performance
    4. Free Capacity Analysis
    5. Bundle Behavior Metrics
    6. Per-Product Summary
    7. Rebalancing Suggestions
    8. Assumption Log
    """
    _check_simulation_permission(current_user)

    config = request.config

    logger.info(
        f"User {current_user.username} running simulation: "
        f"{len(config.operations)} ops, {len(config.demands)} demands, "
        f"mode={config.mode.value}, horizon={config.horizon_days} days"
    )

    # Validate first
    validation_report = validate_simulation_config(config)

    if validation_report.has_errors:
        logger.warning(
            f"Simulation blocked due to validation errors: " f"{[e.message for e in validation_report.errors]}"
        )
        return SimulationResponse(
            success=False,
            results=None,
            validation_report=validation_report,
            message="Validation failed. Please correct errors and retry.",
        )

    try:
        # Track defaults applied for assumption log
        defaults_applied = _track_defaults(config)

        # Run SimPy simulation
        metrics, duration = run_simulation(config)

        logger.info(
            f"Simulation engine completed in {duration:.2f}s: "
            f"throughput={sum(metrics.throughput_by_product.values())}, "
            f"bundles={metrics.bundles_completed}"
        )

        # Calculate all output blocks
        results = calculate_all_blocks(
            config=config,
            metrics=metrics,
            validation_report=validation_report,
            duration_seconds=duration,
            defaults_applied=defaults_applied,
        )

        logger.info(f"Simulation completed successfully for user {current_user.username}")

        return SimulationResponse(
            success=True,
            results=results,
            validation_report=validation_report,
            message=f"Simulation completed in {duration:.2f} seconds",
        )

    except Exception as e:
        logger.exception("Simulation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Simulation failed")


@router.get("/schema")
async def get_input_schema():
    """
    Get the JSON schema for simulation input configuration.

    Returns the Pydantic-generated JSON schema that documents
    all required and optional fields for the simulation configuration.
    """
    return SimulationConfig.model_json_schema()
