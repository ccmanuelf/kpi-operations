"""
Production Line Simulation v2.0 - API Endpoints

Provides REST endpoints for the ephemeral simulation tool.
All endpoints are stateless with no database dependencies.

This is a new v2 implementation that operates as a pure calculator
tool without persisting scenarios to the database.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.jwt import get_current_user
from backend.orm.user import User

from backend.simulation_v2.models import (
    SimulationConfig,
    SimulationRequest,
    SimulationResponse,
    ValidationReport,
    MonteCarloRequest,
    MonteCarloResponse,
    OperatorAllocationRequest,
    OperatorAllocationResponse,
    RebalancingRequest,
    RebalancingResponse,
)
from backend.simulation_v2.validation import validate_simulation_config
from backend.simulation_v2.engine import run_simulation
from backend.simulation_v2.calculations import calculate_all_blocks
from backend.simulation_v2.monte_carlo import run_monte_carlo
from backend.simulation_v2.optimization import (
    MiniZincNotAvailableError,
    MiniZincSolveError,
    is_minizinc_available,
)
from backend.simulation_v2.optimization.operator_allocation import (
    apply_allocation_to_config,
    optimize_operator_allocation,
)
from backend.simulation_v2.optimization.bottleneck_rebalancing import (
    apply_rebalancing_to_config,
    rebalance_bottleneck,
)
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
from typing import Any

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
async def simulation_info() -> Any:
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


@router.post("/run-monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo_endpoint(
    request: MonteCarloRequest, current_user: User = Depends(get_current_user)
) -> MonteCarloResponse:
    """
    Run N replications of the simulation and return aggregated statistics.

    This endpoint:
    1. Validates inputs (returns errors if invalid).
    2. Runs the SimPy engine `n_replications` times with seeded RNG so
       each replication is reproducible (`seed = base_seed + i`).
    3. Aggregates each numeric field of the eight output blocks into
       mean, standard deviation, and 95% CI bounds.
    4. Returns a `sample_run` (the first replication) for non-numeric
       blocks and as a concrete reference shape.

    Use the single-replication `/run` endpoint for fast feedback during
    iteration; use this endpoint when committing to a plan and you want
    uncertainty bounds on the projected metrics.
    """
    _check_simulation_permission(current_user)

    config = request.config

    logger.info(
        f"User {current_user.username} running Monte Carlo: "
        f"{request.n_replications} replications, base_seed={request.base_seed}, "
        f"{len(config.operations)} ops, mode={config.mode.value}"
    )

    try:
        result = run_monte_carlo(
            config=config,
            n_replications=request.n_replications,
            base_seed=request.base_seed,
        )

        validation_report: ValidationReport = result["validation_report"]
        if validation_report.has_errors:
            logger.warning(
                f"Monte Carlo blocked due to validation errors: "
                f"{[e.message for e in validation_report.errors]}"
            )
            return MonteCarloResponse(
                success=False,
                n_replications=0,
                base_seed=request.base_seed,
                total_duration_seconds=0.0,
                aggregated_stats={},
                sample_run=None,
                validation_report=validation_report,
                message="Validation failed. Please correct errors and retry.",
            )

        logger.info(
            f"Monte Carlo completed for user {current_user.username}: "
            f"{result['n_replications']} replications, "
            f"total_duration={result['total_duration_seconds']:.2f}s"
        )

        return MonteCarloResponse(
            success=True,
            n_replications=result["n_replications"],
            base_seed=result["base_seed"],
            total_duration_seconds=result["total_duration_seconds"],
            per_run_duration_seconds=result["per_run_duration_seconds"],
            aggregated_stats=result["aggregated_stats"],
            sample_run=result["sample_run"],
            validation_report=validation_report,
            message=(
                f"Monte Carlo completed: {result['n_replications']} replications "
                f"in {result['total_duration_seconds']:.2f}s"
            ),
        )

    except Exception as e:
        logger.exception("Monte Carlo simulation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Monte Carlo simulation failed",
        )


@router.post("/optimize-operators", response_model=OperatorAllocationResponse)
async def optimize_operators_endpoint(
    request: OperatorAllocationRequest, current_user: User = Depends(get_current_user)
) -> OperatorAllocationResponse:
    """
    Pattern 1 — operator allocation optimization (MiniZinc → SimPy validate).

    Given a SimulationConfig, find the minimum operator count per
    station that meets each station's daily demand under deterministic
    capacity assumptions. When `validate_with_simulation=true`, run a
    single SimPy replication with the optimized allocation so callers
    can compare deterministic prediction vs stochastic engine output.

    Returns 503 with a clear message if the MiniZinc CLI is not
    installed on the host (development environments without it stay
    functional for the rest of the simulation API).
    """
    _check_simulation_permission(current_user)

    if not is_minizinc_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Operator-allocation optimization requires MiniZinc; "
                "the binary is not installed on this server."
            ),
        )

    config = request.config

    logger.info(
        f"User {current_user.username} optimizing operator allocation: "
        f"{len(config.operations)} ops, max_per_op={request.max_operators_per_op}, "
        f"budget={request.total_operators_budget}, "
        f"validate={request.validate_with_simulation}"
    )

    # Validate the SimulationConfig itself before optimizing — surfaces
    # demand/operations mismatches with the same shape the /run path uses.
    validation_report = validate_simulation_config(config)
    if validation_report.has_errors:
        return OperatorAllocationResponse(
            success=False,
            is_optimal=False,
            is_satisfied=False,
            status="validation-failed",
            total_operators_before=sum(int(op.operators or 0) for op in config.operations),
            total_operators_after=0,
            proposals=[],
            solver_message=(
                "Configuration validation failed: "
                + "; ".join(e.message for e in validation_report.errors)
            ),
        )

    try:
        result = optimize_operator_allocation(
            config,
            max_operators_per_op=request.max_operators_per_op,
            total_operators_budget=request.total_operators_budget,
            timeout_seconds=request.timeout_seconds,
        )
    except MiniZincSolveError as e:
        logger.exception("MiniZinc solver error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Solver error: {e}",
        )
    except MiniZincNotAvailableError:
        # Race: the binary check passed but the runner failed. Treat as 503.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MiniZinc CLI became unavailable mid-request.",
        )

    validation_run = None
    if request.validate_with_simulation and result.is_satisfied:
        applied = apply_allocation_to_config(config, result)
        try:
            metrics, duration = run_simulation(applied)
            validation_run = calculate_all_blocks(
                config=applied,
                metrics=metrics,
                validation_report=validation_report,
                duration_seconds=duration,
                defaults_applied=[],
            )
        except Exception:
            # Validation is best-effort; failures don't void the optimization result.
            logger.exception("SimPy validation pass failed for optimized allocation")
            validation_run = None

    logger.info(
        "Operator-allocation optimization done for user=%s: optimal=%s, "
        "before=%d, after=%d",
        current_user.username,
        result.is_optimal,
        result.total_operators_before,
        result.total_operators_after,
    )

    return OperatorAllocationResponse(
        success=result.is_satisfied,
        is_optimal=result.is_optimal,
        is_satisfied=result.is_satisfied,
        status=result.status,
        total_operators_before=result.total_operators_before,
        total_operators_after=result.total_operators_after,
        proposals=[
            {
                "product": p.product,
                "step": p.step,
                "operation": p.operation,
                "machine_tool": p.machine_tool,
                "sam_min": p.sam_min,
                "grade_pct": p.grade_pct,
                "operators_before": p.operators_before,
                "operators_after": p.operators_after,
                "demand_pcs_per_day": p.demand_pcs_per_day,
                "predicted_pcs_per_day": p.predicted_pcs_per_day,
            }
            for p in result.proposals
        ],
        solver_message=result.solver_message,
        validation_run=validation_run,
    )


@router.post("/rebalance-bottlenecks", response_model=RebalancingResponse)
async def rebalance_bottlenecks_endpoint(
    request: RebalancingRequest, current_user: User = Depends(get_current_user)
) -> RebalancingResponse:
    """
    Pattern 2 — bottleneck rebalancing (SimPy detects → MiniZinc solves).

    Take an existing operator allocation (typically one where SimPy
    Block 7 already flagged a bottleneck) and reshuffle operators
    across stations to lift the bottleneck without (by default) growing
    the total head-count.

    `total_delta_max=0` (default) means strict swap. Set higher to
    permit growth. `min_slack_pcs` in the response tells you how much
    headroom the worst station has after rebalancing — negative means
    the demand still can't be met under the given bounds.

    Returns 503 with a clear message if the MiniZinc CLI is not
    installed on the host.
    """
    _check_simulation_permission(current_user)

    if not is_minizinc_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Bottleneck rebalancing requires MiniZinc; the binary is "
                "not installed on this server."
            ),
        )

    config = request.config

    logger.info(
        "User %s rebalancing bottleneck: %d ops, delta=[%d..%d], max_per_op=%d",
        current_user.username,
        len(config.operations),
        request.total_delta_min,
        request.total_delta_max,
        request.max_operators_per_op,
    )

    validation_report = validate_simulation_config(config)
    if validation_report.has_errors:
        return RebalancingResponse(
            success=False,
            is_optimal=False,
            is_satisfied=False,
            status="validation-failed",
            total_operators_before=sum(int(op.operators or 0) for op in config.operations),
            total_operators_after=0,
            total_delta=0,
            min_slack_pcs=0,
            proposals=[],
            solver_message=(
                "Configuration validation failed: "
                + "; ".join(e.message for e in validation_report.errors)
            ),
        )

    try:
        result = rebalance_bottleneck(
            config,
            min_operators_per_op=request.min_operators_per_op,
            max_operators_per_op=request.max_operators_per_op,
            total_delta_max=request.total_delta_max,
            total_delta_min=request.total_delta_min,
            timeout_seconds=request.timeout_seconds,
        )
    except MiniZincSolveError as e:
        logger.exception("MiniZinc solver error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Solver error: {e}",
        )
    except MiniZincNotAvailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MiniZinc CLI became unavailable mid-request.",
        )

    validation_run = None
    if request.validate_with_simulation and result.is_satisfied:
        applied = apply_rebalancing_to_config(config, result)
        try:
            metrics, duration = run_simulation(applied)
            validation_run = calculate_all_blocks(
                config=applied,
                metrics=metrics,
                validation_report=validation_report,
                duration_seconds=duration,
                defaults_applied=[],
            )
        except Exception:
            logger.exception("SimPy validation pass failed for rebalanced allocation")
            validation_run = None

    logger.info(
        "Rebalancing done for user=%s: optimal=%s, total_delta=%d, min_slack=%d",
        current_user.username,
        result.is_optimal,
        result.total_delta,
        result.min_slack_pcs,
    )

    return RebalancingResponse(
        success=result.is_satisfied,
        is_optimal=result.is_optimal,
        is_satisfied=result.is_satisfied,
        status=result.status,
        total_operators_before=result.total_operators_before,
        total_operators_after=result.total_operators_after,
        total_delta=result.total_delta,
        min_slack_pcs=result.min_slack_pcs,
        proposals=[
            {
                "product": p.product,
                "step": p.step,
                "operation": p.operation,
                "machine_tool": p.machine_tool,
                "sam_min": p.sam_min,
                "grade_pct": p.grade_pct,
                "operators_before": p.operators_before,
                "operators_after": p.operators_after,
                "delta": p.delta,
                "demand_pcs_per_day": p.demand_pcs_per_day,
                "predicted_pcs_per_day": p.predicted_pcs_per_day,
                "slack_pcs": p.slack_pcs,
            }
            for p in result.proposals
        ],
        solver_message=result.solver_message,
        validation_run=validation_run,
    )


@router.get("/schema")
async def get_input_schema() -> Any:
    """
    Get the JSON schema for simulation input configuration.

    Returns the Pydantic-generated JSON schema that documents
    all required and optional fields for the simulation configuration.
    """
    return SimulationConfig.model_json_schema()
