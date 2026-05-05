"""
OEECalculationService — Phase 3 dual-view wrapper for OEE.

Composes Availability × Performance × Quality, with assumption-driven
transformations applied to each component's inputs in site_adjusted mode.

Assumption mapping (sourced from CANONICAL_METRIC_DEPENDENCIES):
  - planned_production_time_basis → Availability denominator
        "exclude_scheduled_maintenance" subtracts scheduled_maintenance_hours
        from scheduled_hours
  - setup_treatment → Availability
        "exclude_from_availability" subtracts setup_minutes from
        scheduled_hours instead of letting them sit in downtime_hours
  - ideal_cycle_time_source → Performance
        "rolling_90_day_average" uses the rolling cycle time provided in
        raw inputs; "demonstrated_best" uses the demonstrated-best value;
        default ("engineering_standard") uses the product-master value
  - scrap_classification_rule → Quality
        "rework_counted_as_good" subtracts units_reworked from defect_count
        (rework moves from "defect" to "good")
        "rework_counted_as_bad" leaves defect_count unchanged (rework still
        counts against quality)
        "rework_counted_as_partial" subtracts units_reworked / 2

Standard mode always uses the raw values regardless of any active
assumptions. Site_adjusted mode only diverges if the relevant assumption is
ACTIVE for the period.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.orm.calculation_assumption import CalculationAssumption
from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.orm.user import User
from backend.services.assumption_service import AssumptionService
from backend.services.calculations.oee import OEEInputs, calculate_oee
from backend.services.calculations.performance import (
    PerformanceInputs,
    QualityRateInputs,
    calculate_performance,
    calculate_quality_rate,
)
from backend.services.calculations.availability import (
    AvailabilityInputs,
    calculate_availability,
)
from backend.services.calculations.result import AssumptionApplied, CalculationResult
from backend.services.dual_view.dual_view_result import DualViewResult
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


METRIC_NAME = "oee"


class OEERawInputs(BaseModel):
    """Pre-aggregated inputs for an OEE calculation over a period.

    The service does not fetch DB rows — the caller (route, scheduled job,
    test) supplies these aggregates from whatever source it has. Phase 3
    proves the assumption-injection seam works; integration with the existing
    KPI services that fetch ProductionEntry/QualityEntry rows is a follow-on.
    """

    # Availability inputs
    scheduled_hours: Decimal = Field(ge=Decimal("0"))
    downtime_hours: Decimal = Field(ge=Decimal("0"))
    setup_minutes: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))
    scheduled_maintenance_hours: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))

    # Performance inputs
    units_produced: int = Field(ge=0)
    run_time_hours: Decimal = Field(ge=Decimal("0"))
    ideal_cycle_time_hours: Decimal = Field(gt=Decimal("0"))
    # Optional alternative cycle times for ideal_cycle_time_source assumption
    rolling_90_day_cycle_time_hours: Optional[Decimal] = None
    demonstrated_best_cycle_time_hours: Optional[Decimal] = None

    # Quality inputs
    defect_count: int = Field(ge=0)
    scrap_count: int = Field(ge=0)
    units_reworked: int = Field(ge=0, default=0)


class OEECalculationService:
    """Dual-view OEE calculation. Persists results to METRIC_CALCULATION_RESULT."""

    def __init__(self, db: Session, current_user: User) -> None:
        self.db = db
        self.user = current_user
        self.assumption_svc = AssumptionService(db, current_user)

    # ------------------------------------------------------------------ public

    def calculate(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime,
        raw_inputs: OEERawInputs,
        persist: bool = True,
    ) -> DualViewResult:
        """Compute both standard and site-adjusted OEE for the given period."""

        # Standard mode — always use raw values.
        standard = self._compute(raw_inputs, mode="standard", assumptions={})

        # Site-adjusted mode — fetch active assumptions for this client at
        # period_end, transform inputs, recompute.
        active_assumptions = self.assumption_svc.get_effective_set(client_id=client_id, as_of=period_end)
        adjusted_inputs, applied = self._apply_assumptions(raw_inputs, active_assumptions)
        adjusted = self._compute(adjusted_inputs, mode="site_adjusted", assumptions=active_assumptions)
        adjusted.assumptions_applied = applied  # populate envelope

        snapshot = _build_snapshot(active_assumptions)

        delta = float(adjusted.value - standard.value)
        delta_pct = float((adjusted.value - standard.value) / standard.value * 100) if standard.value != 0 else None

        result_id: Optional[int] = None
        if persist:
            result_id = self._persist(
                client_id=client_id,
                period_start=period_start,
                period_end=period_end,
                standard_value=standard.value,
                site_adjusted_value=adjusted.value,
                delta=delta,
                delta_pct=delta_pct,
                snapshot=snapshot,
                inputs=raw_inputs,
            )

        return DualViewResult(
            metric_name=METRIC_NAME,
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            standard_value=standard.value,
            site_adjusted_value=adjusted.value,
            delta=delta,
            delta_pct=delta_pct,
            assumptions_applied=applied,
            assumptions_snapshot=snapshot,
            calculated_at=datetime.now(tz=timezone.utc),
            result_id=result_id,
        )

    # ----------------------------------------------------------------- helpers

    def _compute(
        self,
        inputs: OEERawInputs,
        mode: str,
        assumptions: dict[str, CalculationAssumption],
    ) -> CalculationResult[Decimal]:
        """Run the three components + the OEE composition. Returns the OEE result."""

        # Availability
        avail = calculate_availability(
            AvailabilityInputs(
                scheduled_hours=inputs.scheduled_hours,
                downtime_hours=inputs.downtime_hours,
            ),
            mode=mode,  # type: ignore[arg-type]
        )

        # Performance
        perf = calculate_performance(
            PerformanceInputs(
                units_produced=inputs.units_produced,
                run_time_hours=inputs.run_time_hours,
                ideal_cycle_time_hours=inputs.ideal_cycle_time_hours,
            ),
            mode=mode,  # type: ignore[arg-type]
        )

        # Quality
        qual = calculate_quality_rate(
            QualityRateInputs(
                units_produced=inputs.units_produced,
                defect_count=inputs.defect_count,
                scrap_count=inputs.scrap_count,
            ),
            mode=mode,  # type: ignore[arg-type]
        )

        # OEE composition
        return calculate_oee(
            OEEInputs(
                availability_pct=avail.value,
                performance_pct=perf.value.performance_pct,
                quality_pct=qual.value.quality_rate_pct,
            ),
            mode=mode,  # type: ignore[arg-type]
        )

    @staticmethod
    def _apply_assumptions(
        inputs: OEERawInputs, active: dict[str, CalculationAssumption]
    ) -> tuple[OEERawInputs, list[AssumptionApplied]]:
        """Build a new OEERawInputs with assumption-driven transformations applied."""

        applied: list[AssumptionApplied] = []
        # Pydantic v2 model_copy preserves validation; mutate via dict.
        data = inputs.model_dump()

        # planned_production_time_basis
        # Convention: scheduled_maintenance_hours is part of downtime_hours
        # (i.e. maintenance is a downtime reason). Excluding it shrinks BOTH
        # the numerator-side downtime and the denominator-side scheduled hours
        # — see docs/assumptions/planned_production_time_basis.md.
        rec = active.get("planned_production_time_basis")
        if rec is not None:
            value = json.loads(rec.value_json)
            applied.append(_to_applied(rec, value))
            if value == "exclude_scheduled_maintenance":
                pm_hours = data["scheduled_maintenance_hours"]
                data["scheduled_hours"] = max(Decimal("0"), data["scheduled_hours"] - pm_hours)
                data["downtime_hours"] = max(Decimal("0"), data["downtime_hours"] - pm_hours)

        # setup_treatment
        rec = active.get("setup_treatment")
        if rec is not None:
            value = json.loads(rec.value_json)
            applied.append(_to_applied(rec, value))
            if value == "exclude_from_availability":
                # Move setup minutes out of downtime AND out of scheduled hours.
                # In the default (count_as_downtime), setup_minutes is already
                # part of downtime_hours so no change is needed.
                setup_hours = data["setup_minutes"] / Decimal("60")
                data["scheduled_hours"] = max(Decimal("0"), data["scheduled_hours"] - setup_hours)
                data["downtime_hours"] = max(Decimal("0"), data["downtime_hours"] - setup_hours)

        # ideal_cycle_time_source
        rec = active.get("ideal_cycle_time_source")
        if rec is not None:
            value = json.loads(rec.value_json)
            applied.append(_to_applied(rec, value))
            if value == "rolling_90_day_average" and inputs.rolling_90_day_cycle_time_hours is not None:
                data["ideal_cycle_time_hours"] = inputs.rolling_90_day_cycle_time_hours
            elif value == "demonstrated_best" and inputs.demonstrated_best_cycle_time_hours is not None:
                data["ideal_cycle_time_hours"] = inputs.demonstrated_best_cycle_time_hours
            # "engineering_standard" → no-op; ideal_cycle_time_hours already
            # comes from the product master per default.

        # scrap_classification_rule
        rec = active.get("scrap_classification_rule")
        if rec is not None:
            value = json.loads(rec.value_json)
            applied.append(_to_applied(rec, value))
            if value == "rework_counted_as_good":
                # Reworked units recovered → don't count them as defects.
                data["defect_count"] = max(0, data["defect_count"] - data["units_reworked"])
            elif value == "rework_counted_as_partial":
                data["defect_count"] = max(0, data["defect_count"] - (data["units_reworked"] // 2))
            # "rework_counted_as_bad" → no-op; rework still in defect_count.

        return OEERawInputs(**data), applied

    def _persist(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime,
        standard_value: Decimal,
        site_adjusted_value: Decimal,
        delta: float,
        delta_pct: Optional[float],
        snapshot: dict[str, Any],
        inputs: OEERawInputs,
    ) -> int:
        record = MetricCalculationResult(
            client_id=client_id,
            metric_name=METRIC_NAME,
            period_start=period_start,
            period_end=period_end,
            standard_value_json=json.dumps(str(standard_value)),
            site_adjusted_value_json=json.dumps(str(site_adjusted_value)),
            delta=delta,
            delta_pct=delta_pct,
            assumptions_snapshot=json.dumps(snapshot),
            inputs_snapshot_json=inputs.model_dump_json(),
            calculated_by=self.user.user_id if self.user else None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info(
            "OEE calculated: client=%s period=[%s, %s] standard=%s adjusted=%s delta=%s",
            client_id,
            period_start,
            period_end,
            standard_value,
            site_adjusted_value,
            delta,
        )
        return record.result_id


# --------------------------------------------------------------- module utils


def _to_applied(rec: CalculationAssumption, value: Any) -> AssumptionApplied:
    return AssumptionApplied(
        name=rec.assumption_name,
        value=value,
        rationale=rec.rationale,
        approved_by=rec.approved_by,
        approved_at=rec.approved_at,
    )


def _build_snapshot(active: dict[str, CalculationAssumption]) -> dict[str, Any]:
    """Compact snapshot for METRIC_CALCULATION_RESULT.assumptions_snapshot."""

    return {
        name: {
            "value": json.loads(rec.value_json),
            "assumption_id": rec.assumption_id,
            "approved_by": rec.approved_by,
            "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
        }
        for name, rec in active.items()
    }
