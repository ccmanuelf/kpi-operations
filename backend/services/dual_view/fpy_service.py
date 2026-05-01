"""
FPYCalculationService — Phase 3 dual-view wrapper for First Pass Yield.

Assumption mapping:
  - scrap_classification_rule → defines whether reworked units count as
    first-pass good.
        "rework_counted_as_bad" (textbook FPY): rework excluded from passed
        "rework_counted_as_good": rework added to total_passed
        "rework_counted_as_partial": half-credit for rework

Standard mode: textbook FPY — total_passed counts only units that passed
inspection without rework or repair.
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
from backend.services.calculations.quality import FPYInputs, calculate_fpy
from backend.services.calculations.result import AssumptionApplied
from backend.services.dual_view.dual_view_result import DualViewResult
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


METRIC_NAME = "fpy"


class FPYRawInputs(BaseModel):
    total_inspected: int = Field(ge=0)
    units_passed_first_time: int = Field(ge=0)  # textbook FPY numerator
    units_reworked: int = Field(ge=0, default=0)


class FPYCalculationService:
    """Dual-view FPY calculation."""

    def __init__(self, db: Session, current_user: User) -> None:
        self.db = db
        self.user = current_user
        self.assumption_svc = AssumptionService(db, current_user)

    def calculate(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime,
        raw_inputs: FPYRawInputs,
        persist: bool = True,
    ) -> DualViewResult:
        # Standard: textbook FPY (no rework credit).
        standard = calculate_fpy(
            FPYInputs(
                total_passed=raw_inputs.units_passed_first_time,
                total_inspected=raw_inputs.total_inspected,
            ),
            mode="standard",
        )

        # Site-adjusted: apply scrap_classification_rule if active.
        active = self.assumption_svc.get_effective_set(client_id=client_id, as_of=period_end)
        applied: list[AssumptionApplied] = []
        adjusted_passed = raw_inputs.units_passed_first_time

        rec = active.get("scrap_classification_rule")
        if rec is not None:
            value = json.loads(rec.value_json)
            applied.append(
                AssumptionApplied(
                    name=rec.assumption_name,
                    value=value,
                    rationale=rec.rationale,
                    approved_by=rec.approved_by,
                    approved_at=rec.approved_at,
                )
            )
            if value == "rework_counted_as_good":
                adjusted_passed = raw_inputs.units_passed_first_time + raw_inputs.units_reworked
            elif value == "rework_counted_as_partial":
                adjusted_passed = raw_inputs.units_passed_first_time + (raw_inputs.units_reworked // 2)
            # "rework_counted_as_bad" → no-op; same as textbook standard.

        adjusted = calculate_fpy(
            FPYInputs(
                total_passed=adjusted_passed,
                total_inspected=raw_inputs.total_inspected,
            ),
            mode="site_adjusted",
        )
        adjusted.assumptions_applied = applied

        snapshot = _build_snapshot(active, only=("scrap_classification_rule",))

        delta = float(adjusted.value - standard.value)
        delta_pct = (
            float((adjusted.value - standard.value) / standard.value * 100)
            if standard.value != 0
            else None
        )

        result_id: Optional[int] = None
        if persist:
            row = MetricCalculationResult(
                client_id=client_id,
                metric_name=METRIC_NAME,
                period_start=period_start,
                period_end=period_end,
                standard_value_json=json.dumps(str(standard.value)),
                site_adjusted_value_json=json.dumps(str(adjusted.value)),
                delta=delta,
                delta_pct=delta_pct,
                assumptions_snapshot=json.dumps(snapshot),
                inputs_snapshot_json=raw_inputs.model_dump_json(),
                calculated_by=self.user.user_id if self.user else None,
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            result_id = row.result_id
            logger.info(
                "FPY calculated: client=%s period=[%s, %s] standard=%s adjusted=%s",
                client_id, period_start, period_end, standard.value, adjusted.value,
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


def _build_snapshot(
    active: dict[str, CalculationAssumption], only: tuple[str, ...]
) -> dict[str, Any]:
    return {
        name: {
            "value": json.loads(rec.value_json),
            "assumption_id": rec.assumption_id,
            "approved_by": rec.approved_by,
            "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
        }
        for name, rec in active.items()
        if name in only
    }
