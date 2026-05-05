"""
Pydantic response schema for the historical calibration endpoint (D4).

The service returns a dict with the SimulationConfig payload plus
per-field provenance and warnings; this module wraps that dict in a
typed response so OpenAPI / Swagger render the shape correctly and
clients get IDE autocomplete.

The `config` field is intentionally typed as `Dict[str, Any]` (rather
than `SimulationConfig`) because we want the calibration output to
flow straight into the simulation form without re-validating server-
side. The form runs its own validation when the user clicks "Run".
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class CalibrationSource(BaseModel):
    """Provenance for a single calibrated field.

    Mirrors the dict shape produced by `_source(...)` in the service.
    Confidence buckets are documented on the service.
    """

    source: str = Field(..., description="Source table or table list (e.g. 'PRODUCTION_ENTRY')")
    sample_size: int = Field(..., ge=0, description="Number of rows aggregated for this field")
    period: str = Field(..., description="Human-readable date range, e.g. '2026-04-01 to 2026-04-30'")
    confidence: str = Field(
        ...,
        description="One of: high (>=14), medium (5-13), low (1-4), none (0)",
    )


class CalibrationPeriod(BaseModel):
    """Echo of the period the calibration covers."""

    start: str = Field(..., description="ISO date (YYYY-MM-DD) of the first day in the window")
    end: str = Field(..., description="ISO date (YYYY-MM-DD) of the last day in the window")
    days: int = Field(..., ge=1, description="Inclusive day count")


class CalibrationResponse(BaseModel):
    """Top-level response from `GET /api/v2/simulation/calibration`.

    The shape is deliberately a thin envelope around the service dict:
    the frontend can copy `config` straight into the simulation form,
    and `sources` / `warnings` drive the "where did this come from"
    chips and the orange banner the UI shows above the form.
    """

    client_id: str = Field(..., description="Client this calibration was computed for")
    period: CalibrationPeriod
    config: Dict[str, Any] = Field(
        ...,
        description=(
            "SimulationConfig-shaped dict. Fields: operations[], schedule, "
            "demands[], breakdowns[], mode, horizon_days. Kept loose because "
            "the simulation engine validates on submit, not on calibration."
        ),
    )
    sources: Dict[str, CalibrationSource] = Field(
        ...,
        description=(
            "Per-field provenance keyed by dotted path "
            "(e.g. 'products.Polo Shirt', 'schedule', 'breakdowns'). The UI "
            "uses these to render confidence chips next to each calibrated "
            "field."
        ),
    )
    warnings: List[str] = Field(
        default_factory=list,
        description=(
            "Human-readable warnings the planner should see above the form "
            "(missing standards, empty production window, FPD% defaulted, "
            "etc.). Empty list means the calibration is fully sourced."
        ),
    )
