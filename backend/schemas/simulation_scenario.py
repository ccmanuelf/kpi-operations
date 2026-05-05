"""
Pydantic schemas for SimulationScenario (D3 — scenario persistence).

The wire shape closely tracks the ORM but uses pure Python types so
Pydantic can serialize cleanly. `config_json` and `last_run_summary`
are typed `Dict[str, Any]` rather than the rich Pydantic models from
`backend.simulation_v2.models` because:
  1. Engine versions evolve; old persisted configs may have fields
     no longer recognised by the latest Pydantic models. We accept
     them on load and let the engine validate when actually used.
  2. The `config` is opaque to this module — we never inspect its
     structure, just round-trip it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SimulationScenarioCreate(BaseModel):
    """Body for POST /api/v2/simulation/scenarios."""

    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    client_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description=(
            "Client to scope the scenario to. NULL = global template "
            "(admin only). Non-admin users can only set this to one of "
            "their assigned clients."
        ),
    )
    config_json: Dict[str, Any] = Field(
        ...,
        description=(
            "The full SimulationConfig payload (operations, schedule, "
            "demands, breakdowns, mode, horizon_days). Validated by the "
            "engine when the scenario is run, not on save."
        ),
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Free-form labels for filtering (e.g. ['baseline', 'optimized']).",
    )


class SimulationScenarioUpdate(BaseModel):
    """Body for PUT /api/v2/simulation/scenarios/{id}.

    All fields optional; only provided fields are updated. Note that
    setting `is_active=False` soft-deletes the scenario (same effect as
    DELETE).
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    config_json: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class SimulationScenarioResponse(BaseModel):
    """Read-back shape for GET / POST / PUT responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: Optional[str]
    name: str
    description: Optional[str]
    config_json: Dict[str, Any]
    last_run_summary: Optional[Dict[str, Any]] = None
    last_run_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    is_active: bool
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None


class SimulationScenarioSummary(BaseModel):
    """Lightweight shape for the list view — omits the full config_json
    (potentially MB-size) and just exposes headline fields the UI needs
    to render the scenarios table.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: Optional[str]
    name: str
    description: Optional[str]
    last_run_summary: Optional[Dict[str, Any]] = None
    last_run_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    is_active: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None
