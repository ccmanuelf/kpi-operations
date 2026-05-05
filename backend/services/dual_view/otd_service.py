"""
OTDCalculationService — Phase 3 dual-view wrapper for On-Time Delivery.

Assumption mapping:
  - otd_carrier_buffer_pct → extends the "on-time" definition by N% of the
    order's planned lead time. With buffer=5, an order delivered up to 5% of
    its lead time after the planned date still counts as on-time.

Standard mode: orders are on-time iff `delay_pct <= 0`.
Site_adjusted mode: orders are on-time iff `delay_pct <= buffer/100`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.orm.calculation_assumption import CalculationAssumption
from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.orm.user import User
from backend.services.assumption_service import AssumptionService
from backend.services.calculations.otd import OTDInputs, calculate_otd
from backend.services.calculations.result import AssumptionApplied
from backend.services.dual_view.dual_view_result import DualViewResult
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


METRIC_NAME = "otd"


class OrderDelay(BaseModel):
    """Per-order delay as a fraction of planned lead time. Negative = early."""

    delay_pct: Decimal


class OTDRawInputs(BaseModel):
    """One delay value per completed order in the period."""

    orders: List[OrderDelay] = Field(default_factory=list)


class OTDCalculationService:
    """Dual-view OTD calculation."""

    def __init__(self, db: Session, current_user: User) -> None:
        self.db = db
        self.user = current_user
        self.assumption_svc = AssumptionService(db, current_user)

    def calculate(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime,
        raw_inputs: OTDRawInputs,
        persist: bool = True,
    ) -> DualViewResult:
        # Standard: zero buffer.
        standard_value = self._otd_pct(raw_inputs, buffer_pct=Decimal("0"))

        # Site-adjusted: read otd_carrier_buffer_pct if active.
        active = self.assumption_svc.get_effective_set(client_id=client_id, as_of=period_end)
        applied: list[AssumptionApplied] = []
        buffer_pct = Decimal("0")

        rec = active.get("otd_carrier_buffer_pct")
        if rec is not None:
            value = json.loads(rec.value_json)
            buffer_pct = Decimal(str(value))
            applied.append(
                AssumptionApplied(
                    name=rec.assumption_name,
                    value=value,
                    rationale=rec.rationale,
                    approved_by=rec.approved_by,
                    approved_at=rec.approved_at,
                )
            )

        adjusted_value = self._otd_pct(raw_inputs, buffer_pct=buffer_pct)

        snapshot = _build_snapshot(active, only=("otd_carrier_buffer_pct",))

        delta = float(adjusted_value - standard_value)
        delta_pct = float((adjusted_value - standard_value) / standard_value * 100) if standard_value != 0 else None

        result_id: Optional[int] = None
        if persist:
            row = MetricCalculationResult(
                client_id=client_id,
                metric_name=METRIC_NAME,
                period_start=period_start,
                period_end=period_end,
                standard_value_json=json.dumps(str(standard_value)),
                site_adjusted_value_json=json.dumps(str(adjusted_value)),
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
                "OTD calculated: client=%s period=[%s, %s] standard=%s adjusted=%s",
                client_id,
                period_start,
                period_end,
                standard_value,
                adjusted_value,
            )

        return DualViewResult(
            metric_name=METRIC_NAME,
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            standard_value=standard_value,
            site_adjusted_value=adjusted_value,
            delta=delta,
            delta_pct=delta_pct,
            assumptions_applied=applied,
            assumptions_snapshot=snapshot,
            calculated_at=datetime.now(tz=timezone.utc),
            result_id=result_id,
        )

    @staticmethod
    def _otd_pct(raw: OTDRawInputs, buffer_pct: Decimal) -> Decimal:
        """Pure helper: compute OTD% given a buffer threshold (in percent units)."""

        total = len(raw.orders)
        if total == 0:
            return Decimal("0.00")

        threshold = buffer_pct / Decimal("100")
        on_time = sum(1 for o in raw.orders if o.delay_pct <= threshold)

        result = calculate_otd(OTDInputs(on_time_orders=on_time, total_orders=total), mode="standard")
        return result.value


def _build_snapshot(active: dict[str, CalculationAssumption], only: tuple[str, ...]) -> dict[str, Any]:
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
