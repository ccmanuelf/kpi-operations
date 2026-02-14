"""
FPY (First Pass Yield) and RTY (Rolled Throughput Yield) Calculations
PHASE 4: Quality yield metrics

FPY = (Units Passed First Time / Total Units Processed) * 100
RTY = FPY1 × FPY2 × FPY3 × ... × FPYn (for all process steps)

Phase 6.6 Enhancement: RTY can be calculated at JOB (line item) level within work orders
Phase 1.2: Added pure calculation functions for service layer separation
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from decimal import Decimal
from typing import Optional, List
import math

from backend.schemas.quality_entry import QualityEntry
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.job import Job


# =============================================================================
# PURE CALCULATION FUNCTIONS (No Database Access)
# Phase 1.2: These functions can be unit tested without database
# =============================================================================


def calculate_fpy_pure(total_passed: int, total_inspected: int) -> Decimal:
    """
    Pure FPY (First Pass Yield) calculation - no database access.

    Formula: (Units Passed First Time / Total Units Inspected) * 100

    CRITICAL: First Pass units should EXCLUDE both rework AND repair.
    This function assumes total_passed already excludes rework/repair.

    Args:
        total_passed: Units that passed first time (without rework/repair)
        total_inspected: Total units inspected

    Returns:
        FPY percentage as Decimal

    Examples:
        >>> calculate_fpy_pure(95, 100)
        Decimal('95.00')  # 95% first pass yield
    """
    if total_inspected <= 0:
        return Decimal("0")

    fpy = (Decimal(str(total_passed)) / Decimal(str(total_inspected))) * 100
    return fpy.quantize(Decimal("0.01"))


def calculate_rty_pure(step_fpys: List[Decimal]) -> Decimal:
    """
    Pure RTY (Rolled Throughput Yield) calculation - no database access.

    Formula: FPY_step1 × FPY_step2 × ... × FPY_stepN
    (all FPYs as decimals, not percentages)

    Args:
        step_fpys: List of FPY percentages for each step

    Returns:
        RTY percentage as Decimal

    Examples:
        >>> calculate_rty_pure([Decimal("95"), Decimal("90"), Decimal("98")])
        Decimal('83.79')  # 0.95 × 0.90 × 0.98 × 100 = 83.79%
    """
    if not step_fpys:
        return Decimal("0")

    rty_decimal = Decimal("1.0")

    for fpy in step_fpys:
        # Convert percentage to decimal and multiply
        fpy_decimal = fpy / 100
        rty_decimal = rty_decimal * fpy_decimal

    # Convert back to percentage
    rty_percentage = rty_decimal * 100
    return rty_percentage.quantize(Decimal("0.01"))


def calculate_job_yield_pure(completed_quantity: int, quantity_scrapped: int) -> Decimal:
    """
    Pure job yield calculation - no database access.

    Formula: (completed_quantity - quantity_scrapped) / completed_quantity * 100

    Args:
        completed_quantity: Total completed quantity
        quantity_scrapped: Quantity scrapped

    Returns:
        Yield percentage as Decimal

    Examples:
        >>> calculate_job_yield_pure(100, 5)
        Decimal('95.00')  # 95% yield
    """
    if completed_quantity <= 0:
        return Decimal("0")

    good = completed_quantity - quantity_scrapped
    good = max(0, good)  # Ensure non-negative

    yield_pct = (Decimal(str(good)) / Decimal(str(completed_quantity))) * 100
    return yield_pct.quantize(Decimal("0.01"))


def calculate_recovery_rate_pure(units_reworked: int, units_repaired: int, units_scrapped: int) -> Decimal:
    """
    Pure recovery rate calculation - no database access.

    Recovery Rate = (Rework + Repair) / (Rework + Repair + Scrap) * 100

    Args:
        units_reworked: Units that were reworked (recovered in-line)
        units_repaired: Units requiring significant repair
        units_scrapped: Units that couldn't be recovered

    Returns:
        Recovery rate percentage

    Examples:
        >>> calculate_recovery_rate_pure(10, 5, 5)
        Decimal('75.00')  # 15 recovered out of 20 = 75%
    """
    total_failed = units_reworked + units_repaired + units_scrapped

    if total_failed <= 0:
        return Decimal("100")  # Nothing failed, 100% recovery

    recovered = units_reworked + units_repaired
    rate = (Decimal(str(recovered)) / Decimal(str(total_failed))) * 100
    return rate.quantize(Decimal("0.01"))


def calculate_fpy(
    db: Session, product_id: int, start_date: date, end_date: date, inspection_stage: Optional[str] = None
) -> tuple[Decimal, int, int]:
    """
    Calculate First Pass Yield for a specific inspection stage

    FPY = (Units Passed First Time / Units Inspected) * 100

    CRITICAL: First Pass units EXCLUDE both rework AND repair
    - Rework: Units that failed but were corrected in-line (quick fix)
    - Repair: Units that require significant resources/external repair

    Returns: (fpy_percentage, first_pass_good, total_units)
    """
    from datetime import datetime

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Note: QualityEntry doesn't have product_id - use work_order/job based filtering
    # For now, get all quality entries in date range
    query = db.query(QualityEntry).filter(
        and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime)
    )

    if inspection_stage:
        query = query.filter(QualityEntry.inspection_stage == inspection_stage)

    inspections = query.all()

    if not inspections:
        return (Decimal("0"), 0, 0)

    total_units = sum(i.units_inspected or 0 for i in inspections)
    total_passed = sum(i.units_passed or 0 for i in inspections)
    total_rework = sum(i.units_reworked or 0 for i in inspections)
    total_repair = sum(i.units_requiring_repair or 0 for i in inspections)

    # First Pass Good = units that passed WITHOUT needing any rework or repair
    # If units_passed already excludes rework/repair, use it directly
    # Otherwise: first_pass_good = total_passed - total_rework - total_repair
    # We assume units_passed represents units that passed first time (per schema design)
    first_pass_good = total_passed

    if total_units > 0:
        fpy = (Decimal(str(first_pass_good)) / Decimal(str(total_units))) * 100
    else:
        fpy = Decimal("0")

    return (fpy, first_pass_good, total_units)


def calculate_fpy_with_repair_breakdown(
    db: Session, product_id: int, start_date: date, end_date: date, inspection_stage: Optional[str] = None
) -> dict:
    """
    Calculate FPY with detailed repair vs rework breakdown

    This function provides granular metrics for Phase 6.5 requirements:
    - True FPY (excludes both rework and repair)
    - Rework impact (quick fixes, in-line corrections)
    - Repair impact (significant resource usage, external fixes)

    Returns: Dict with FPY and repair/rework breakdown
    """
    from datetime import datetime

    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    query = db.query(QualityEntry).filter(
        and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime)
    )

    if inspection_stage:
        query = query.filter(QualityEntry.inspection_stage == inspection_stage)

    inspections = query.all()

    if not inspections:
        return {
            "fpy_percentage": Decimal("0"),
            "first_pass_good": 0,
            "total_inspected": 0,
            "units_reworked": 0,
            "units_requiring_repair": 0,
            "units_scrapped": 0,
            "rework_rate": Decimal("0"),
            "repair_rate": Decimal("0"),
            "scrap_rate": Decimal("0"),
            "recovered_units": 0,  # Rework + Repair (recovered vs scrapped)
            "recovery_rate": Decimal("0"),
        }

    total_inspected = sum(i.units_inspected or 0 for i in inspections)
    total_passed = sum(i.units_passed or 0 for i in inspections)
    total_rework = sum(i.units_reworked or 0 for i in inspections)
    total_repair = sum(i.units_requiring_repair or 0 for i in inspections)
    total_scrap = sum(i.units_scrapped or 0 for i in inspections)

    # Calculate rates
    if total_inspected > 0:
        fpy = (Decimal(str(total_passed)) / Decimal(str(total_inspected))) * 100
        rework_rate = (Decimal(str(total_rework)) / Decimal(str(total_inspected))) * 100
        repair_rate = (Decimal(str(total_repair)) / Decimal(str(total_inspected))) * 100
        scrap_rate = (Decimal(str(total_scrap)) / Decimal(str(total_inspected))) * 100
    else:
        fpy = rework_rate = repair_rate = scrap_rate = Decimal("0")

    # Recovered units = rework + repair (items that were saved vs scrapped)
    recovered_units = total_rework + total_repair
    if (total_rework + total_repair + total_scrap) > 0:
        recovery_rate = (Decimal(str(recovered_units)) / Decimal(str(total_rework + total_repair + total_scrap))) * 100
    else:
        recovery_rate = Decimal("100")  # If nothing failed, 100% recovery

    return {
        "fpy_percentage": fpy,
        "first_pass_good": total_passed,
        "total_inspected": total_inspected,
        "units_reworked": total_rework,
        "units_requiring_repair": total_repair,
        "units_scrapped": total_scrap,
        "rework_rate": rework_rate,
        "repair_rate": repair_rate,
        "scrap_rate": scrap_rate,
        "recovered_units": recovered_units,
        "recovery_rate": recovery_rate,
    }


def calculate_rty(
    db: Session, product_id: int, start_date: date, end_date: date, process_steps: Optional[List[str]] = None
) -> tuple[Decimal, List[dict]]:
    """
    Calculate Rolled Throughput Yield across all process steps

    RTY = FPY_step1 × FPY_step2 × ... × FPY_stepN

    process_steps: List of inspection stages (e.g., ['Incoming', 'In-Process', 'Final'])

    Returns: (rty_percentage, step_details)
    """

    if not process_steps:
        # Default apparel manufacturing stages
        process_steps = ["Incoming", "In-Process", "Final"]

    step_yields = []
    rty = Decimal("1.0")  # Start at 100% (1.0)

    for step in process_steps:
        fpy, good, total = calculate_fpy(db, product_id, start_date, end_date, inspection_stage=step)

        # Convert percentage to decimal for multiplication
        fpy_decimal = fpy / 100

        # Multiply for RTY
        rty = rty * fpy_decimal

        step_yields.append({"step": step, "fpy_percentage": fpy, "first_pass_good": good, "total_units": total})

    # Convert RTY back to percentage
    rty_percentage = rty * 100

    return (rty_percentage, step_yields)


def calculate_rty_with_repair_impact(
    db: Session, product_id: int, start_date: date, end_date: date, process_steps: Optional[List[str]] = None
) -> dict:
    """
    Calculate RTY with repair impact analysis

    This enhanced RTY calculation shows:
    - Standard RTY (rolled across all stages)
    - Repair impact on throughput (how much repair affects overall yield)
    - Rework vs Repair breakdown per stage

    Returns: Dict with RTY and repair impact metrics
    """
    if not process_steps:
        process_steps = ["Incoming", "In-Process", "Final"]

    step_details = []
    rty = Decimal("1.0")
    total_rework_across_stages = 0
    total_repair_across_stages = 0
    total_scrap_across_stages = 0
    total_inspected_across_stages = 0

    for step in process_steps:
        breakdown = calculate_fpy_with_repair_breakdown(db, product_id, start_date, end_date, inspection_stage=step)

        # Convert FPY percentage to decimal for multiplication
        fpy_decimal = breakdown["fpy_percentage"] / 100
        rty = rty * fpy_decimal

        # Accumulate totals
        total_rework_across_stages += breakdown["units_reworked"]
        total_repair_across_stages += breakdown["units_requiring_repair"]
        total_scrap_across_stages += breakdown["units_scrapped"]
        total_inspected_across_stages += breakdown["total_inspected"]

        step_details.append(
            {
                "step": step,
                "fpy_percentage": breakdown["fpy_percentage"],
                "first_pass_good": breakdown["first_pass_good"],
                "total_inspected": breakdown["total_inspected"],
                "units_reworked": breakdown["units_reworked"],
                "units_requiring_repair": breakdown["units_requiring_repair"],
                "units_scrapped": breakdown["units_scrapped"],
                "rework_rate": breakdown["rework_rate"],
                "repair_rate": breakdown["repair_rate"],
            }
        )

    # Convert RTY back to percentage
    rty_percentage = rty * 100

    # Calculate overall repair impact on throughput
    # Repair Impact = Total resources lost to repair / Total inspected
    if total_inspected_across_stages > 0:
        repair_impact = (Decimal(str(total_repair_across_stages)) / Decimal(str(total_inspected_across_stages))) * 100
        rework_impact = (Decimal(str(total_rework_across_stages)) / Decimal(str(total_inspected_across_stages))) * 100
    else:
        repair_impact = rework_impact = Decimal("0")

    return {
        "rty_percentage": rty_percentage,
        "step_details": step_details,
        "total_rework": total_rework_across_stages,
        "total_repair": total_repair_across_stages,
        "total_scrap": total_scrap_across_stages,
        "rework_impact_percentage": rework_impact,
        "repair_impact_percentage": repair_impact,
        "throughput_loss_percentage": repair_impact + rework_impact,
        "interpretation": get_rty_interpretation(rty_percentage, repair_impact),
    }


def get_rty_interpretation(rty: Decimal, repair_impact: Decimal) -> str:
    """Generate human-readable interpretation of RTY and repair impact"""
    if rty >= 95 and repair_impact <= 2:
        return "Excellent: High yield with minimal repair requirements"
    elif rty >= 90 and repair_impact <= 5:
        return "Good: Strong yield, monitor repair trends"
    elif rty >= 80:
        if repair_impact > 10:
            return "Warning: Acceptable yield but high repair rate indicates process issues"
        return "Acceptable: Meeting baseline but improvement opportunity exists"
    else:
        if repair_impact > 15:
            return "Critical: Low yield with excessive repair - immediate process review required"
        return "Needs Improvement: Below target, investigate root causes"


def calculate_process_yield(db: Session, product_id: int, start_date: date, end_date: date) -> dict:
    """
    Calculate overall process yield including scrap rate

    Process Yield = ((Total Produced - Total Scrapped) / Total Produced) * 100
    """
    from datetime import datetime

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get production data
    production = (
        db.query(ProductionEntry)
        .filter(
            and_(
                ProductionEntry.product_id == product_id,
                ProductionEntry.production_date >= start_datetime,
                ProductionEntry.production_date <= end_datetime,
            )
        )
        .all()
    )

    total_produced = sum(p.units_produced or 0 for p in production)
    total_scrap = sum(p.scrap_count or 0 for p in production)
    total_defects = sum(p.defect_count or 0 for p in production)

    # Get quality entry data
    inspections = (
        db.query(QualityEntry)
        .filter(and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime))
        .all()
    )

    inspection_scrap = sum(i.units_scrapped or 0 for i in inspections)
    total_scrap += inspection_scrap

    # Calculate yield
    if total_produced > 0:
        good_units = total_produced - total_scrap - total_defects
        process_yield = (Decimal(str(good_units)) / Decimal(str(total_produced))) * 100
        scrap_rate = (Decimal(str(total_scrap)) / Decimal(str(total_produced))) * 100
    else:
        process_yield = Decimal("0")
        scrap_rate = Decimal("0")
        good_units = 0

    return {
        "process_yield": process_yield,
        "scrap_rate": scrap_rate,
        "total_produced": total_produced,
        "good_units": good_units,
        "total_scrap": total_scrap,
        "total_defects": total_defects,
    }


def calculate_defect_escape_rate(db: Session, product_id: int, start_date: date, end_date: date) -> Decimal:
    """
    Calculate Defect Escape Rate

    Escape Rate = (Defects Found at Final / Total Defects Found) * 100

    Measures how many defects escape earlier inspection stages
    """
    from datetime import datetime

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get all quality entries
    all_inspections = (
        db.query(QualityEntry)
        .filter(and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime))
        .all()
    )

    if not all_inspections:
        return Decimal("0")

    # Defects found at final inspection
    final_defects = sum(i.units_defective or 0 for i in all_inspections if i.inspection_stage == "Final")

    # Total defects found
    total_defects = sum(i.units_defective or 0 for i in all_inspections)

    if total_defects > 0:
        escape_rate = (Decimal(str(final_defects)) / Decimal(str(total_defects))) * 100
    else:
        escape_rate = Decimal("0")

    return escape_rate


def calculate_quality_score(db: Session, product_id: int, start_date: date, end_date: date) -> dict:
    """
    Calculate comprehensive quality score (0-100)

    Weighted combination of:
    - FPY (40%)
    - RTY (30%)
    - Scrap Rate (20%)
    - Defect Escape Rate (10%)
    """

    # Get metrics
    fpy, _, _ = calculate_fpy(db, product_id, start_date, end_date)
    rty, _ = calculate_rty(db, product_id, start_date, end_date)
    process_data = calculate_process_yield(db, product_id, start_date, end_date)
    escape_rate = calculate_defect_escape_rate(db, product_id, start_date, end_date)

    # Scrap rate (inverse score - lower is better)
    scrap_score = max(Decimal("0"), 100 - process_data["scrap_rate"])

    # Escape rate (inverse score - lower is better)
    escape_score = max(Decimal("0"), 100 - escape_rate)

    # Weighted quality score
    quality_score = (
        fpy * Decimal("0.40") + rty * Decimal("0.30") + scrap_score * Decimal("0.20") + escape_score * Decimal("0.10")
    )

    # Determine grade
    if quality_score >= 95:
        grade = "A+"
        interpretation = "Excellent - World Class Quality"
    elif quality_score >= 90:
        grade = "A"
        interpretation = "Excellent Quality"
    elif quality_score >= 85:
        grade = "B+"
        interpretation = "Very Good Quality"
    elif quality_score >= 80:
        grade = "B"
        interpretation = "Good Quality"
    elif quality_score >= 75:
        grade = "C+"
        interpretation = "Acceptable Quality"
    elif quality_score >= 70:
        grade = "C"
        interpretation = "Needs Improvement"
    else:
        grade = "D"
        interpretation = "Poor Quality - Immediate Action Required"

    return {
        "quality_score": quality_score,
        "grade": grade,
        "interpretation": interpretation,
        "components": {"fpy": fpy, "rty": rty, "scrap_rate": process_data["scrap_rate"], "escape_rate": escape_rate},
    }


# ============================================================================
# PHASE 6.6: JOB-Level RTY Calculations
# ============================================================================


def calculate_job_yield(db: Session, job_id: str) -> dict:
    """
    Calculate yield metrics for a specific job (line item).

    Phase 6.6: Job-level yield calculation using JOB table data.

    Yield = (completed_quantity - quantity_scrapped) / completed_quantity * 100

    Args:
        db: Database session
        job_id: Job ID to calculate yield for

    Returns:
        Dictionary with job yield metrics
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()

    if not job:
        return {
            "job_id": job_id,
            "yield_percentage": Decimal("0"),
            "completed_quantity": 0,
            "quantity_scrapped": 0,
            "good_quantity": 0,
            "error": "Job not found",
        }

    completed = job.completed_quantity or 0
    scrapped = job.quantity_scrapped or 0
    good = completed - scrapped

    if completed > 0:
        yield_pct = (Decimal(str(good)) / Decimal(str(completed))) * 100
    else:
        yield_pct = Decimal("0")

    return {
        "job_id": job_id,
        "operation_name": job.operation_name,
        "sequence_number": job.sequence_number,
        "part_number": job.part_number,
        "yield_percentage": yield_pct,
        "completed_quantity": completed,
        "quantity_scrapped": scrapped,
        "good_quantity": good,
    }


def calculate_work_order_job_rty(db: Session, work_order_id: str, client_id: Optional[str] = None) -> dict:
    """
    Calculate RTY across all jobs (line items) within a work order.

    Phase 6.6: Job-level RTY calculation.

    RTY = Yield_Job1 × Yield_Job2 × ... × Yield_JobN

    This provides more granular insight than work-order-level RTY by
    showing which operations within the work order have yield issues.

    Args:
        db: Database session
        work_order_id: Work order ID to calculate RTY for
        client_id: Optional client ID for multi-tenant filtering

    Returns:
        Dictionary with RTY breakdown by job
    """
    # Get all jobs for the work order, ordered by sequence
    query = db.query(Job).filter(Job.work_order_id == work_order_id)

    if client_id:
        query = query.filter(Job.client_id_fk == client_id)

    jobs = query.order_by(Job.sequence_number).all()

    if not jobs:
        return {
            "work_order_id": work_order_id,
            "rty_percentage": Decimal("0"),
            "job_count": 0,
            "jobs": [],
            "total_scrapped": 0,
            "bottleneck_job": None,
            "error": "No jobs found for work order",
        }

    # Calculate yield for each job
    rty_decimal = Decimal("1.0")
    job_yields = []
    total_scrapped = 0
    lowest_yield_job = None
    lowest_yield = Decimal("100")

    for job in jobs:
        completed = job.completed_quantity or 0
        scrapped = job.quantity_scrapped or 0
        good = completed - scrapped
        total_scrapped += scrapped

        if completed > 0:
            yield_pct = (Decimal(str(good)) / Decimal(str(completed))) * 100
            yield_decimal = Decimal(str(good)) / Decimal(str(completed))
        else:
            yield_pct = Decimal("0")
            yield_decimal = Decimal("0")

        # Track bottleneck (lowest yield job)
        if yield_pct < lowest_yield and completed > 0:
            lowest_yield = yield_pct
            lowest_yield_job = {
                "job_id": job.job_id,
                "operation_name": job.operation_name,
                "yield_percentage": float(yield_pct),
            }

        # Multiply for RTY (only if job has completed work)
        if completed > 0:
            rty_decimal = rty_decimal * yield_decimal

        job_yields.append(
            {
                "job_id": job.job_id,
                "operation_name": job.operation_name,
                "sequence_number": job.sequence_number,
                "part_number": job.part_number,
                "planned_quantity": job.planned_quantity,
                "completed_quantity": completed,
                "quantity_scrapped": scrapped,
                "good_quantity": good,
                "yield_percentage": float(yield_pct),
                "is_completed": bool(job.is_completed),
            }
        )

    # Convert RTY back to percentage
    rty_percentage = rty_decimal * 100

    return {
        "work_order_id": work_order_id,
        "rty_percentage": float(rty_percentage),
        "job_count": len(jobs),
        "jobs": job_yields,
        "total_scrapped": total_scrapped,
        "bottleneck_job": lowest_yield_job,
        "interpretation": get_job_rty_interpretation(rty_percentage),
    }


def calculate_job_rty_summary(db: Session, start_date: date, end_date: date, client_id: Optional[str] = None) -> dict:
    """
    Calculate RTY summary across all jobs within a date range.

    Phase 6.6: Aggregate job-level RTY for reporting.

    Args:
        db: Database session
        start_date: Start of date range
        end_date: End of date range
        client_id: Optional client ID for multi-tenant filtering

    Returns:
        Dictionary with aggregate job RTY metrics
    """
    from datetime import datetime
    from sqlalchemy import func

    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get completed jobs in date range
    query = db.query(Job).filter(
        and_(Job.completed_date >= start_datetime, Job.completed_date <= end_datetime, Job.is_completed == 1)
    )

    if client_id:
        query = query.filter(Job.client_id_fk == client_id)

    jobs = query.all()

    if not jobs:
        return {
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "total_jobs_completed": 0,
            "total_units_completed": 0,
            "total_units_scrapped": 0,
            "average_job_yield": Decimal("0"),
            "overall_yield": Decimal("0"),
            "jobs_below_target": 0,
            "top_scrap_operations": [],
        }

    # Aggregate metrics
    total_completed = sum(j.completed_quantity or 0 for j in jobs)
    total_scrapped = sum(j.quantity_scrapped or 0 for j in jobs)
    total_good = total_completed - total_scrapped

    # Calculate yields
    job_yields = []
    operation_scrap = {}

    for job in jobs:
        completed = job.completed_quantity or 0
        scrapped = job.quantity_scrapped or 0

        if completed > 0:
            yield_pct = (Decimal(str(completed - scrapped)) / Decimal(str(completed))) * 100
            job_yields.append(yield_pct)

        # Track scrap by operation
        op_name = job.operation_name or "Unknown"
        if op_name not in operation_scrap:
            operation_scrap[op_name] = 0
        operation_scrap[op_name] += scrapped

    # Calculate average job yield
    if job_yields:
        avg_yield = sum(job_yields) / len(job_yields)
    else:
        avg_yield = Decimal("0")

    # Calculate overall yield
    if total_completed > 0:
        overall_yield = (Decimal(str(total_good)) / Decimal(str(total_completed))) * 100
    else:
        overall_yield = Decimal("0")

    # Jobs below 95% target
    jobs_below_target = sum(1 for y in job_yields if y < 95)

    # Top scrap operations
    top_scrap = sorted(operation_scrap.items(), key=lambda x: x[1], reverse=True)[:5]
    top_scrap_ops = [{"operation": op, "units_scrapped": scrapped} for op, scrapped in top_scrap]

    return {
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "total_jobs_completed": len(jobs),
        "total_units_completed": total_completed,
        "total_units_scrapped": total_scrapped,
        "total_good_units": total_good,
        "average_job_yield": float(avg_yield),
        "overall_yield": float(overall_yield),
        "jobs_below_target": jobs_below_target,
        "jobs_meeting_target": len(jobs) - jobs_below_target,
        "top_scrap_operations": top_scrap_ops,
        "interpretation": get_job_rty_interpretation(avg_yield),
    }


def get_job_rty_interpretation(rty: Decimal) -> str:
    """Generate human-readable interpretation of job-level RTY"""
    rty_float = float(rty) if isinstance(rty, Decimal) else rty

    if rty_float >= 98:
        return "Excellent: World-class job-level yield"
    elif rty_float >= 95:
        return "Good: Meeting standard targets"
    elif rty_float >= 90:
        return "Acceptable: Minor improvement opportunities"
    elif rty_float >= 85:
        return "Warning: Below target, investigate bottleneck operations"
    else:
        return "Critical: Significant yield loss, immediate action required"
