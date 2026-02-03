"""
Production Line Simulation v2.0 - Input Validation

Implements two-phase validation:
1. Schema validation (handled by Pydantic) - data types, required fields, basic constraints
2. Domain validation - manufacturing-specific rules and consistency checks

All validation is stateless with no database dependencies.
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict
import difflib

from .models import (
    SimulationConfig,
    OperationInput,
    DemandInput,
    ValidationReport,
    ValidationIssue,
    ValidationSeverity,
    DemandMode,
)
from .constants import (
    DEMAND_CONSISTENCY_TOLERANCE_PCT,
    MIX_PERCENTAGE_TOLERANCE,
    MACHINE_TOOL_SIMILARITY_THRESHOLD,
    THEORETICAL_CAPACITY_BUFFER,
    MAX_PRODUCTS,
    MAX_OPERATIONS_PER_PRODUCT,
    MAX_TOTAL_OPERATIONS,
)


def validate_simulation_config(config: SimulationConfig) -> ValidationReport:
    """
    Perform comprehensive validation of simulation configuration.

    Args:
        config: Complete simulation configuration

    Returns:
        ValidationReport with errors, warnings, info, and summary statistics
    """
    report = ValidationReport()

    # Collect statistics and group data
    products: Set[str] = set()
    machine_tools: Set[str] = set()
    operations_by_product: Dict[str, List[OperationInput]] = defaultdict(list)

    for op in config.operations:
        products.add(op.product)
        machine_tools.add(op.machine_tool)
        operations_by_product[op.product].append(op)

    # Set statistics
    report.products_count = len(products)
    report.operations_count = len(config.operations)
    report.machine_tools_count = len(machine_tools)

    # Run all validation checks
    _validate_configuration_limits(config, products, report)
    _validate_operation_sequences(operations_by_product, report)
    _validate_product_consistency(operations_by_product, config.demands, report)
    _validate_machine_tool_consistency(config.operations, report)
    _validate_operators_configuration(operations_by_product, report)
    _validate_demand_configuration(config, report)
    _validate_schedule_reasonableness(config.schedule, report)
    _validate_breakdown_configuration(config, machine_tools, report)
    _validate_theoretical_capacity(config, operations_by_product, report)

    # Set final status
    report.is_valid = len(report.errors) == 0
    report.can_proceed = report.is_valid

    return report


def _validate_configuration_limits(
    config: SimulationConfig,
    products: Set[str],
    report: ValidationReport
) -> None:
    """Check configuration doesn't exceed system limits."""

    if len(products) > MAX_PRODUCTS:
        report.errors.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="limits",
            message=f"Too many products ({len(products)}). Maximum allowed is {MAX_PRODUCTS}",
            recommendation=f"Reduce to {MAX_PRODUCTS} or fewer products"
        ))

    if len(config.operations) > MAX_TOTAL_OPERATIONS:
        report.errors.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="limits",
            message=f"Too many total operations ({len(config.operations)}). Maximum is {MAX_TOTAL_OPERATIONS}",
            recommendation="Reduce total operations or simplify product definitions"
        ))


def _validate_operation_sequences(
    operations_by_product: Dict[str, List[OperationInput]],
    report: ValidationReport
) -> None:
    """Validate operation step sequences are sequential without gaps."""

    for product, ops in operations_by_product.items():
        if len(ops) > MAX_OPERATIONS_PER_PRODUCT:
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="limits",
                product=product,
                message=f"Product '{product}' has {len(ops)} operations. Maximum is {MAX_OPERATIONS_PER_PRODUCT}",
                recommendation="Reduce operations or combine similar steps"
            ))
            continue

        steps = sorted([op.step for op in ops])

        # Check for duplicates
        if len(steps) != len(set(steps)):
            duplicates = [s for s in steps if steps.count(s) > 1]
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="sequence",
                product=product,
                message=f"Product '{product}' has duplicate step numbers: {list(set(duplicates))}",
                recommendation="Ensure each step number is unique within the product"
            ))
            continue

        # Check for gaps (steps should be sequential from first step)
        if steps:
            first_step = steps[0]
            expected = list(range(first_step, first_step + len(steps)))
            if steps != expected:
                missing = set(expected) - set(steps)
                if missing:
                    report.errors.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="sequence",
                        product=product,
                        message=f"Product '{product}' has gaps in step sequence. Missing steps: {sorted(missing)}",
                        recommendation="Steps must be sequential without gaps"
                    ))


def _validate_product_consistency(
    operations_by_product: Dict[str, List[OperationInput]],
    demands: List[DemandInput],
    report: ValidationReport
) -> None:
    """Validate products in operations match products in demand."""

    ops_products = set(operations_by_product.keys())
    demand_products = {d.product for d in demands}

    # Products in demand but not in operations - ERROR
    orphan_demand = demand_products - ops_products
    for product in orphan_demand:
        report.errors.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="product_consistency",
            product=product,
            message=f"Product '{product}' has demand specified but no operations defined",
            recommendation="Add operations for this product or remove from demand configuration"
        ))

    # Products in operations but not in demand - WARNING
    orphan_ops = ops_products - demand_products
    for product in orphan_ops:
        report.warnings.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category="product_consistency",
            product=product,
            message=f"Product '{product}' has operations defined but no demand specified",
            recommendation="This product will be excluded from simulation. Add demand or remove operations."
        ))


def _validate_machine_tool_consistency(
    operations: List[OperationInput],
    report: ValidationReport
) -> None:
    """Check for potential typos in machine tool names using similarity detection."""

    tool_counts: Dict[str, int] = defaultdict(int)
    for op in operations:
        tool_counts[op.machine_tool] += 1

    tools = list(tool_counts.keys())

    # Check for near-matches that might be typos
    checked_pairs: Set[Tuple[str, str]] = set()
    for i, tool1 in enumerate(tools):
        for tool2 in tools[i + 1:]:
            # Skip if already checked
            pair = tuple(sorted([tool1, tool2]))
            if pair in checked_pairs:
                continue
            checked_pairs.add(pair)

            # Check similarity
            ratio = difflib.SequenceMatcher(
                None,
                tool1.lower().strip(),
                tool2.lower().strip()
            ).ratio()

            if MACHINE_TOOL_SIMILARITY_THRESHOLD <= ratio < 1.0:
                report.warnings.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="machine_tool",
                    message=(
                        f"Similar machine/tool names found: '{tool1}' ({tool_counts[tool1]} uses) "
                        f"and '{tool2}' ({tool_counts[tool2]} uses)"
                    ),
                    recommendation=(
                        "If these are the same machine, standardize the name. "
                        "Different names create separate resource pools."
                    )
                ))


def _validate_operators_configuration(
    operations_by_product: Dict[str, List[OperationInput]],
    report: ValidationReport
) -> None:
    """Check operator configuration for potential issues."""

    # Group by machine_tool to check consistency
    tool_operations: Dict[str, List[OperationInput]] = defaultdict(list)
    for product, ops in operations_by_product.items():
        for op in ops:
            tool_operations[op.machine_tool].append(op)

    for tool, ops in tool_operations.items():
        operator_counts = set(op.operators for op in ops)
        if len(operator_counts) > 1:
            # Multiple different operator counts for same tool
            report.info.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                category="operators",
                message=(
                    f"Machine '{tool}' has varying operator counts across operations: {sorted(operator_counts)}. "
                    f"Total capacity will be pooled ({sum(op.operators for op in ops)} operators)."
                ),
                recommendation="This is informational - resource pooling will sum all operators for this machine."
            ))


def _validate_demand_configuration(
    config: SimulationConfig,
    report: ValidationReport
) -> None:
    """Validate demand values and mode consistency."""

    if config.mode == DemandMode.MIX_DRIVEN:
        _validate_mix_driven_demand(config, report)
    else:
        _validate_demand_driven_demand(config, report)


def _validate_mix_driven_demand(
    config: SimulationConfig,
    report: ValidationReport
) -> None:
    """Validate mix-driven mode demand configuration."""

    # Check mix percentages sum to 100
    total_mix = sum(d.mix_share_pct or 0 for d in config.demands)

    if abs(total_mix - 100.0) > MIX_PERCENTAGE_TOLERANCE:
        report.errors.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="demand",
            field="mix_share_pct",
            message=f"Mix percentages sum to {total_mix:.1f}%, must equal 100%",
            recommendation="Adjust mix_share_pct values to sum to exactly 100"
        ))

    # Check that all products have mix_share_pct
    for demand in config.demands:
        if demand.mix_share_pct is None or demand.mix_share_pct == 0:
            report.warnings.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="demand",
                product=demand.product,
                message=f"Product '{demand.product}' has no mix_share_pct in mix-driven mode",
                recommendation="Set mix_share_pct > 0 or this product will have zero demand"
            ))


def _validate_demand_driven_demand(
    config: SimulationConfig,
    report: ValidationReport
) -> None:
    """Validate demand-driven mode demand configuration."""

    for demand in config.demands:
        # Check if any demand is specified
        if not demand.daily_demand and not demand.weekly_demand:
            report.warnings.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="demand",
                product=demand.product,
                message=f"Product '{demand.product}' has no demand specified",
                recommendation="Set daily_demand or weekly_demand, or this product will be excluded"
            ))
            continue

        # Check consistency between daily and weekly
        if demand.daily_demand and demand.weekly_demand:
            expected_weekly = demand.daily_demand * config.schedule.work_days
            diff_pct = abs(expected_weekly - demand.weekly_demand) / demand.weekly_demand * 100

            if diff_pct > DEMAND_CONSISTENCY_TOLERANCE_PCT:
                report.warnings.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="demand",
                    product=demand.product,
                    message=(
                        f"Daily demand ({demand.daily_demand:.0f}) × work days ({config.schedule.work_days}) "
                        f"= {expected_weekly:.0f}, but weekly demand is {demand.weekly_demand:.0f} "
                        f"({diff_pct:.1f}% difference)"
                    ),
                    recommendation="Weekly demand will be used as authoritative. Verify values are correct."
                ))


def _validate_schedule_reasonableness(schedule, report: ValidationReport) -> None:
    """Validate schedule is reasonable for manufacturing."""

    # Info about shifts not fully utilized
    if schedule.shifts_enabled >= 2 and schedule.shift2_hours == 0:
        report.info.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            category="schedule",
            message="shifts_enabled is 2 or more but shift2_hours is 0",
            recommendation="Set shift2_hours > 0 to utilize second shift"
        ))

    if schedule.shifts_enabled >= 3 and schedule.shift3_hours == 0:
        report.info.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            category="schedule",
            message="shifts_enabled is 3 but shift3_hours is 0",
            recommendation="Set shift3_hours > 0 to utilize third shift"
        ))


def _validate_breakdown_configuration(
    config: SimulationConfig,
    machine_tools: Set[str],
    report: ValidationReport
) -> None:
    """Validate breakdown configuration matches operations."""

    if not config.breakdowns:
        return

    for breakdown in config.breakdowns:
        if breakdown.machine_tool not in machine_tools:
            report.warnings.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="breakdown",
                field="machine_tool",
                message=(
                    f"Breakdown configured for '{breakdown.machine_tool}' "
                    f"which is not used in any operation"
                ),
                recommendation="This breakdown configuration will have no effect. Remove or fix the machine name."
            ))


def _validate_theoretical_capacity(
    config: SimulationConfig,
    operations_by_product: Dict[str, List[OperationInput]],
    report: ValidationReport
) -> None:
    """Pre-check if demand is theoretically achievable."""

    daily_hours = config.schedule.daily_planned_hours

    for demand in config.demands:
        if demand.product not in operations_by_product:
            continue

        ops = operations_by_product[demand.product]

        # Calculate total SAM per unit (adjusted for grade/FPD)
        total_adjusted_sam = 0.0
        for op in ops:
            base_sam = op.sam_min
            # Apply average adjustments (without variability)
            fpd_multiplier = op.fpd_pct / 100
            grade_multiplier = (100 - op.grade_pct) / 100
            adjusted_sam = base_sam * (1 + fpd_multiplier + grade_multiplier)
            total_adjusted_sam += adjusted_sam

        # Get demand
        daily_demand = demand.daily_demand
        if not daily_demand and demand.weekly_demand:
            daily_demand = demand.weekly_demand / config.schedule.work_days

        if not daily_demand or daily_demand == 0:
            continue

        # Calculate theoretical hours needed (this is simplified - doesn't account for parallelism)
        # This gives a rough lower bound
        hours_needed = (total_adjusted_sam * daily_demand) / 60  # Convert minutes to hours

        if hours_needed > daily_hours * THEORETICAL_CAPACITY_BUFFER:
            report.warnings.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="theoretical_capacity",
                product=demand.product,
                message=(
                    f"Product '{demand.product}': Theoretical minimum hours needed ({hours_needed:.1f}h) "
                    f"exceeds available hours ({daily_hours:.1f}h) even under optimal conditions"
                ),
                recommendation=(
                    f"Demand of {daily_demand:.0f} pieces/day may be unachievable. "
                    "Consider reducing demand, adding shifts, or improving SAM times."
                )
            ))
