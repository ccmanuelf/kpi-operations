"""Response contracts for /api/kpi.

Declared types are what close the Decimal class: MariaDB hands back Decimal,
Pydantic renders Decimal as a JSON string under `Any`, and a declared `float`
coerces it instead. See docs/superpowers/specs/2026-08-25-response-model-refactor-design.md.
"""

from pydantic import BaseModel


class TrendPoint(BaseModel):
    """One point on any KPI trend series.

    Shared by 9 endpoints (absenteeism, availability, efficiency, oee,
    on-time-delivery, performance, quality, throughput-time, wip-aging) --
    measured, not assumed: 8 of the 9 returned exactly ("date", "value") on
    2026-08-25 against the committed golden master; on-time-delivery/trend
    returned no rows under that seed (empty capture carries no shape), so its
    membership is confirmed by reading backend/routes/kpi/trends.py::get_otd_trend
    instead, which returns the identical `{"date": str(r.date), "value": ...}`
    shape as its siblings.
    """

    date: str
    value: float
