"""
Alert Calculation Engine
Generates intelligent alerts based on predictions, thresholds, and patterns
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import uuid

from backend.calculations.predictions import auto_forecast, ForecastResult


@dataclass
class AlertGenerationResult:
    """Result of alert generation check"""

    should_alert: bool
    severity: str  # info, warning, critical, urgent
    title: str
    message: str
    recommendation: Optional[str] = None
    confidence: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    threshold_value: Optional[Decimal] = None
    predicted_value: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = None


def generate_alert_id() -> str:
    """Generate unique alert ID"""
    return f"ALT-{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def check_threshold_breach(
    current_value: Decimal,
    target: Decimal,
    warning_threshold: Optional[Decimal],
    critical_threshold: Optional[Decimal],
    higher_is_better: bool = True,
) -> Optional[str]:
    """
    Check if a value breaches thresholds

    Returns:
        None if no breach, or 'warning', 'critical', 'urgent' severity
    """
    if higher_is_better:
        # For metrics where higher is better (efficiency, FPY)
        # Check for urgent FIRST (far below target - more severe than critical)
        if current_value < target * Decimal("0.5"):
            return "urgent"
        if critical_threshold and current_value <= critical_threshold:
            return "critical"
        if warning_threshold and current_value <= warning_threshold:
            return "warning"
    else:
        # For metrics where lower is better (DPMO, PPM, downtime)
        # Check for urgent FIRST (far above target - more severe than critical)
        if current_value > target * Decimal("5"):
            return "urgent"
        if critical_threshold and current_value >= critical_threshold:
            return "critical"
        if warning_threshold and current_value >= warning_threshold:
            return "warning"

    return None


def generate_efficiency_alert(
    current_efficiency: Decimal,
    target: Decimal = Decimal("85"),
    warning_threshold: Decimal = Decimal("80"),
    critical_threshold: Decimal = Decimal("70"),
    historical_values: Optional[List[Decimal]] = None,
    client_name: Optional[str] = None,
) -> Optional[AlertGenerationResult]:
    """
    Generate efficiency alert based on current value and trend

    Args:
        current_efficiency: Current efficiency percentage
        target: Target efficiency (default 85%)
        warning_threshold: Warning level (default 80%)
        critical_threshold: Critical level (default 70%)
        historical_values: Historical efficiency values for trend analysis
        client_name: Client name for context
    """
    severity = check_threshold_breach(
        current_efficiency, target, warning_threshold, critical_threshold, higher_is_better=True
    )

    if not severity:
        # Check for declining trend even if above threshold
        if historical_values and len(historical_values) >= 5:
            recent = historical_values[-5:]
            if all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
                # 5 consecutive declining values
                severity = "warning"
                return AlertGenerationResult(
                    should_alert=True,
                    severity=severity,
                    title="Efficiency Declining Trend",
                    message=f"Efficiency has declined for 5 consecutive periods. Current: {current_efficiency}%, Target: {target}%",
                    recommendation="Investigate production bottlenecks and operator performance",
                    current_value=current_efficiency,
                    threshold_value=target,
                    metadata={"trend": "declining", "periods": 5},
                )
        return None

    context = f" for {client_name}" if client_name else ""

    if severity == "urgent":
        title = f"URGENT: Critical Efficiency Drop{context}"
        message = f"Efficiency at {current_efficiency}% - significantly below target of {target}%"
        recommendation = (
            "Immediate intervention required. Check for equipment failures, staffing issues, or material problems."
        )
    elif severity == "critical":
        title = f"Critical: Low Efficiency{context}"
        message = f"Efficiency at {current_efficiency}% is below critical threshold of {critical_threshold}%"
        recommendation = "Review production line performance. Consider overtime or additional resources."
    else:  # warning
        title = f"Warning: Efficiency Below Target{context}"
        message = f"Efficiency at {current_efficiency}% is below warning threshold of {warning_threshold}%"
        recommendation = "Monitor closely and identify improvement opportunities."

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=title,
        message=message,
        recommendation=recommendation,
        current_value=current_efficiency,
        threshold_value=target,
        metadata={"warning": warning_threshold, "critical": critical_threshold},
    )


def generate_otd_risk_alert(
    work_order_id: str,
    client_name: str,
    due_date: datetime,
    current_completion_percent: Decimal,
    planned_completion_percent: Decimal,
    days_remaining: int,
) -> Optional[AlertGenerationResult]:
    """
    Generate OTD risk alert based on completion progress vs plan

    Args:
        work_order_id: Work order identifier
        client_name: Client name
        due_date: Due date for the order
        current_completion_percent: Current completion %
        planned_completion_percent: Where we should be %
        days_remaining: Days until due date
    """
    # Calculate risk score (0-100, higher = more risk)
    completion_gap = planned_completion_percent - current_completion_percent

    # Risk factors:
    # 1. How far behind schedule
    # 2. How many days remaining
    # 3. Trend (if declining, higher risk)

    risk_score = Decimal("0")

    # Gap penalty (10 points per % behind)
    if completion_gap > 0:
        risk_score += min(completion_gap * Decimal("10"), Decimal("50"))

    # Time pressure (more risk as deadline approaches)
    if days_remaining <= 1:
        risk_score += Decimal("40")
    elif days_remaining <= 3:
        risk_score += Decimal("25")
    elif days_remaining <= 7:
        risk_score += Decimal("10")

    # Determine severity
    if risk_score >= 80:
        severity = "urgent"
        title = f"URGENT: Order {work_order_id} at High Risk of Late Delivery"
        recommendation = "Prioritize this order immediately. Consider overtime or resource reallocation."
    elif risk_score >= 60:
        severity = "critical"
        title = f"Critical: Order {work_order_id} Behind Schedule"
        recommendation = "Accelerate production. Review bottlenecks and allocate additional resources."
    elif risk_score >= 40:
        severity = "warning"
        title = f"Warning: Order {work_order_id} Trending Late"
        recommendation = "Monitor progress closely. Plan corrective action if trend continues."
    else:
        return None  # No alert needed

    message = (
        f"Client: {client_name}\n"
        f"Due: {due_date.strftime('%Y-%m-%d')}\n"
        f"Progress: {current_completion_percent}% (should be {planned_completion_percent}%)\n"
        f"Days Remaining: {days_remaining}\n"
        f"Risk Score: {risk_score}"
    )

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=title,
        message=message,
        recommendation=recommendation,
        current_value=current_completion_percent,
        threshold_value=planned_completion_percent,
        confidence=Decimal("100") - risk_score,  # Confidence in on-time delivery
        metadata={
            "risk_score": float(risk_score),
            "days_remaining": days_remaining,
            "due_date": due_date.isoformat(),
            "work_order_id": work_order_id,
            "client_name": client_name,
        },
    )


def generate_quality_alert(
    kpi_type: str,  # fpy, rty, dpmo, ppm
    current_value: Decimal,
    target: Decimal,
    warning_threshold: Optional[Decimal] = None,
    critical_threshold: Optional[Decimal] = None,
    historical_values: Optional[List[Decimal]] = None,
    product_line: Optional[str] = None,
) -> Optional[AlertGenerationResult]:
    """
    Generate quality KPI alert

    Args:
        kpi_type: Type of quality metric (fpy, rty, dpmo, ppm)
        current_value: Current KPI value
        target: Target value
        warning_threshold: Warning level
        critical_threshold: Critical level
        historical_values: Historical values for trend
        product_line: Product line for context
    """
    # Determine direction (higher is better for FPY/RTY, lower is better for DPMO/PPM)
    higher_is_better = kpi_type.lower() in ["fpy", "rty"]

    # Set default thresholds if not provided
    if higher_is_better:
        warning_threshold = warning_threshold or (target * Decimal("0.95"))
        critical_threshold = critical_threshold or (target * Decimal("0.90"))
    else:
        warning_threshold = warning_threshold or (target * Decimal("1.5"))
        critical_threshold = critical_threshold or (target * Decimal("2.0"))

    severity = check_threshold_breach(
        current_value, target, warning_threshold, critical_threshold, higher_is_better=higher_is_better
    )

    # Check for trend even if no threshold breach
    trend_direction = "stable"
    if historical_values and len(historical_values) >= 3:
        recent = historical_values[-3:]
        if higher_is_better:
            if recent[-1] < recent[0]:
                trend_direction = "declining"
            elif recent[-1] > recent[0]:
                trend_direction = "improving"
        else:
            if recent[-1] > recent[0]:
                trend_direction = "declining"
            elif recent[-1] < recent[0]:
                trend_direction = "improving"

    if not severity and trend_direction == "declining":
        severity = "info"
    elif not severity:
        return None

    kpi_name = {
        "fpy": "First Pass Yield",
        "rty": "Rolled Throughput Yield",
        "dpmo": "Defects Per Million Opportunities",
        "ppm": "Parts Per Million",
    }.get(kpi_type.lower(), kpi_type.upper())

    unit = "%" if kpi_type.lower() in ["fpy", "rty"] else ""
    context = f" - {product_line}" if product_line else ""

    if severity == "urgent":
        title = f"URGENT: {kpi_name} Critical{context}"
        message = f"{kpi_name} at {current_value}{unit} is severely {'below' if higher_is_better else 'above'} target of {target}{unit}"
        recommendation = "Stop production for quality review. Investigate root cause immediately."
    elif severity == "critical":
        title = f"Critical: {kpi_name} Below Acceptable Level{context}"
        message = f"{kpi_name} at {current_value}{unit} breached critical threshold"
        recommendation = "Implement immediate quality control measures. Review recent process changes."
    elif severity == "warning":
        title = f"Warning: {kpi_name} Approaching Limit{context}"
        message = (
            f"{kpi_name} at {current_value}{unit} is {'below warning' if higher_is_better else 'above warning'} level"
        )
        recommendation = "Increase inspection frequency. Identify potential quality issues."
    else:  # info
        title = f"Info: {kpi_name} Trending {'Down' if higher_is_better else 'Up'}{context}"
        message = f"{kpi_name} showing declining trend over recent periods"
        recommendation = "Monitor closely for continued deterioration."

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=title,
        message=message,
        recommendation=recommendation,
        current_value=current_value,
        threshold_value=target,
        metadata={
            "kpi_type": kpi_type,
            "trend": trend_direction,
            "warning": float(warning_threshold) if warning_threshold else None,
            "critical": float(critical_threshold) if critical_threshold else None,
            "product_line": product_line,
        },
    )


def generate_capacity_alert(
    load_percent: Decimal,
    optimal_min: Decimal = Decimal("85"),
    optimal_max: Decimal = Decimal("95"),
    predicted_idle_days: Optional[int] = None,
    overtime_hours_needed: Optional[Decimal] = None,
    bottleneck_station: Optional[str] = None,
) -> Optional[AlertGenerationResult]:
    """
    Generate capacity planning alert based on load percentage

    Based on research: Load% decisions from capacity planning studies:
    - Load < 90%: May have idle time, consider reducing hours
    - Load 90-100%: Optimal utilization
    - Load > 100%: Need overtime or cannot meet demand

    Args:
        load_percent: Current capacity load percentage
        optimal_min: Minimum optimal load (default 85%)
        optimal_max: Maximum optimal load (default 95%)
        predicted_idle_days: Predicted idle days if underutilized
        overtime_hours_needed: Required overtime if overloaded
        bottleneck_station: Identified bottleneck station
    """
    if load_percent < Decimal("70"):
        severity = "warning"
        title = "Capacity Alert: Significant Underutilization"
        message = f"Load at {load_percent}% - factory significantly underutilized"
        recommendation = "Consider reducing working hours to cut costs or seek additional orders."
        status = "underutilized"
    elif load_percent < optimal_min:
        severity = "info"
        title = "Capacity Alert: Below Optimal Load"
        message = f"Load at {load_percent}% - below optimal range ({optimal_min}-{optimal_max}%)"
        recommendation = "Monitor order pipeline. May have minor idle capacity."
        status = "underutilized"
    elif load_percent <= optimal_max:
        # Optimal - no alert unless there's a bottleneck
        if bottleneck_station:
            severity = "info"
            title = f"Bottleneck Detected: {bottleneck_station}"
            message = f"Load at {load_percent}% (optimal), but bottleneck at {bottleneck_station}"
            recommendation = f"Address bottleneck at {bottleneck_station} to improve flow."
            status = "optimal"
        else:
            return None  # No alert for optimal state without issues
    elif load_percent <= Decimal("105"):
        severity = "warning"
        title = "Capacity Alert: Near Maximum"
        message = f"Load at {load_percent}% - approaching maximum capacity"
        recommendation = "Plan overtime or temporary resources if orders increase."
        status = "near_max"
    else:
        severity = "critical"
        title = "Capacity Alert: Overloaded"
        message = f"Load at {load_percent}% - CANNOT meet demand with current capacity"
        recommendation = (
            "Immediate action required: authorize overtime, hire temporary workers, or negotiate delivery dates."
        )
        status = "overloaded"

    # Enhance message with details
    details = []
    if predicted_idle_days:
        details.append(f"Predicted idle days: {predicted_idle_days}")
    if overtime_hours_needed:
        details.append(f"Overtime needed: {overtime_hours_needed} hours")
    if bottleneck_station:
        details.append(f"Bottleneck: {bottleneck_station}")

    if details:
        message += "\n" + "\n".join(details)

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=title,
        message=message,
        recommendation=recommendation,
        current_value=load_percent,
        threshold_value=optimal_max,
        metadata={
            "status": status,
            "load_percent": float(load_percent),
            "idle_days": predicted_idle_days,
            "overtime_hours": float(overtime_hours_needed) if overtime_hours_needed else None,
            "bottleneck": bottleneck_station,
        },
    )


def generate_prediction_based_alert(
    kpi_key: str,
    historical_values: List[Decimal],
    target: Decimal,
    warning_threshold: Optional[Decimal] = None,
    critical_threshold: Optional[Decimal] = None,
    forecast_periods: int = 7,
    higher_is_better: bool = True,
) -> Optional[AlertGenerationResult]:
    """
    Generate alert based on predicted future values

    Args:
        kpi_key: KPI identifier
        historical_values: Historical KPI values
        target: Target value
        warning_threshold: Warning level
        critical_threshold: Critical level
        forecast_periods: Days to forecast
        higher_is_better: True if higher values are better
    """
    if len(historical_values) < 5:
        return None  # Need enough data for prediction

    # Generate forecast
    try:
        forecast: ForecastResult = auto_forecast(historical_values, forecast_periods)
    except Exception:
        return None

    # Check if any prediction breaches thresholds
    worst_prediction = None
    worst_period = None

    for i, pred in enumerate(forecast.predictions):
        severity = check_threshold_breach(pred, target, warning_threshold, critical_threshold, higher_is_better)
        if severity:
            if worst_prediction is None or (
                (higher_is_better and pred < worst_prediction) or (not higher_is_better and pred > worst_prediction)
            ):
                worst_prediction = pred
                worst_period = i + 1

    if worst_prediction is None:
        return None

    # Determine alert severity based on how soon and how bad
    severity = check_threshold_breach(worst_prediction, target, warning_threshold, critical_threshold, higher_is_better)

    if worst_period <= 3:
        # Issue predicted within 3 days - escalate
        if severity == "warning":
            severity = "critical"
        elif severity == "critical":
            severity = "urgent"

    confidence = (
        forecast.confidence_scores[worst_period - 1]
        if worst_period <= len(forecast.confidence_scores)
        else Decimal("50")
    )

    kpi_display = kpi_key.upper().replace("_", " ")

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=f"Predicted {severity.title()}: {kpi_display} in {worst_period} Days",
        message=(
            f"{kpi_display} predicted to reach {worst_prediction} in {worst_period} days\n"
            f"Current: {historical_values[-1]}\n"
            f"Target: {target}\n"
            f"Confidence: {confidence}%"
        ),
        recommendation=f"Take preventive action now to avoid {kpi_display} {'dropping below' if higher_is_better else 'exceeding'} acceptable levels.",
        current_value=historical_values[-1],
        threshold_value=target,
        predicted_value=worst_prediction,
        confidence=confidence,
        metadata={
            "forecast_method": forecast.method,
            "forecast_accuracy": float(forecast.accuracy_score),
            "all_predictions": [float(p) for p in forecast.predictions],
            "worst_period_days": worst_period,
        },
    )


def generate_attendance_alert(
    absenteeism_rate: Decimal,
    target_rate: Decimal = Decimal("5"),
    warning_threshold: Decimal = Decimal("8"),
    critical_threshold: Decimal = Decimal("12"),
    floating_pool_available: int = 0,
    coverage_needed: int = 0,
) -> Optional[AlertGenerationResult]:
    """
    Generate attendance/absenteeism alert

    Args:
        absenteeism_rate: Current absenteeism percentage
        target_rate: Target absenteeism rate (default 5%)
        warning_threshold: Warning level (default 8%)
        critical_threshold: Critical level (default 12%)
        floating_pool_available: Available floating pool workers
        coverage_needed: Workers needed for coverage
    """
    severity = check_threshold_breach(
        absenteeism_rate,
        target_rate,
        warning_threshold,
        critical_threshold,
        higher_is_better=False,  # Lower absenteeism is better
    )

    if not severity:
        return None

    coverage_gap = coverage_needed - floating_pool_available

    if severity == "urgent" or (severity == "critical" and coverage_gap > 5):
        title = "URGENT: Critical Absenteeism Level"
        message = f"Absenteeism at {absenteeism_rate}% - production capacity severely impacted"
        recommendation = (
            "Activate all floating pool resources. Consider temporary workers or overtime for present staff."
        )
    elif severity == "critical":
        title = "Critical: High Absenteeism"
        message = f"Absenteeism at {absenteeism_rate}% exceeds critical threshold of {critical_threshold}%"
        recommendation = "Deploy floating pool workers immediately. Review attendance policy."
    else:  # warning
        title = "Warning: Elevated Absenteeism"
        message = f"Absenteeism at {absenteeism_rate}% above normal levels"
        recommendation = "Monitor situation. Prepare floating pool assignments if trend continues."

    if coverage_gap > 0:
        message += f"\nCoverage gap: {coverage_gap} workers short"
    elif floating_pool_available > coverage_needed:
        message += f"\nFloating pool can cover: {floating_pool_available} available"

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=title,
        message=message,
        recommendation=recommendation,
        current_value=absenteeism_rate,
        threshold_value=target_rate,
        metadata={
            "floating_pool_available": floating_pool_available,
            "coverage_needed": coverage_needed,
            "coverage_gap": coverage_gap,
        },
    )


def generate_hold_alert(
    pending_holds_count: int, oldest_hold_hours: Optional[int] = None, total_units_on_hold: int = 0
) -> Optional[AlertGenerationResult]:
    """
    Generate alert for pending hold approvals

    Args:
        pending_holds_count: Number of holds awaiting approval
        oldest_hold_hours: Hours since oldest pending hold was created
        total_units_on_hold: Total units affected by holds
    """
    if pending_holds_count == 0:
        return None

    # Determine severity based on count and age
    if oldest_hold_hours and oldest_hold_hours > 24:
        severity = "critical"
        title = "Critical: Hold Pending Over 24 Hours"
        recommendation = "Review and approve/reject immediately to prevent production delays."
    elif pending_holds_count > 5:
        severity = "warning"
        title = f"Warning: {pending_holds_count} Holds Pending Approval"
        recommendation = "Process pending holds to maintain production flow."
    elif oldest_hold_hours and oldest_hold_hours > 8:
        severity = "warning"
        title = "Warning: Hold Aging"
        recommendation = "Review pending hold before end of shift."
    else:
        severity = "info"
        title = f"Info: {pending_holds_count} Hold(s) Require Approval"
        recommendation = "Review holds at your convenience."

    message = f"{pending_holds_count} hold(s) pending approval"
    if oldest_hold_hours:
        message += f"\nOldest pending: {oldest_hold_hours} hours"
    if total_units_on_hold:
        message += f"\nTotal units on hold: {total_units_on_hold}"

    return AlertGenerationResult(
        should_alert=True,
        severity=severity,
        title=title,
        message=message,
        recommendation=recommendation,
        metadata={
            "pending_count": pending_holds_count,
            "oldest_hours": oldest_hold_hours,
            "units_on_hold": total_units_on_hold,
        },
    )
