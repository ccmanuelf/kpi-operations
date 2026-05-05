"""
SimulationScenario — persistent records for SimPy V2 + MiniZinc scenarios.

Stores the full SimulationConfig as JSON plus an optional cached
last-run summary so list views can show throughput / efficiency / OEE
without re-running the engine. Used by the Simulation V2 frontend's
Save/Load workflow.

Multi-tenant: every record carries `client_id`.
Soft delete: `is_active` flag preserves audit trail; consumer queries
filter on `is_active = TRUE` by default.

Why a single JSON column for the config rather than normalised tables?
The SimulationConfig has 4 nested arrays (operations, demands, breakdowns,
schedule) with rich per-operation parameters. Normalising would mean
~5 tables and many joins on every load. The config is opaque to the
database — only the simulator engine reads its structure — so a JSON
blob is appropriate.

Trade-offs:
  - PRO: simple shape, one table, easy versioning of the engine
  - PRO: matches CapacityScenario pattern already in use here
  - CON: can't query "all scenarios with > 5 products" via SQL alone
        (we'd have to load + filter in app code)

If the latter matters in future, we can add denormalised summary
columns (`product_count`, `total_demand_pcs`) populated on save without
breaking the JSON shape.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class SimulationScenario(Base):
    """SIMULATION_SCENARIO table — persisted SimPy V2 / MiniZinc configs."""

    __tablename__ = "SIMULATION_SCENARIO"
    __table_args__ = (
        Index("ix_simulation_scenario_client_active", "client_id", "is_active"),
        Index("ix_simulation_scenario_client_name", "client_id", "name"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation — CRITICAL. NULL allowed for global / cross-
    # client scenarios that admins may want to save (e.g. a baseline
    # template), though the typical record has a real client_id.
    client_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True
    )

    # Identification
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The full SimulationConfig payload as the engine consumes it.
    # Shape matches `backend.simulation_v2.models.SimulationConfig.model_dump()`.
    config_json: Mapped[Any] = mapped_column(JSON, nullable=False)

    # Optional last-run result summary (a flat dict of headline metrics).
    # Populated by POST /scenarios/{id}/run; null until the scenario is
    # executed at least once. Frontend list view reads this to show
    # "last throughput / efficiency / OEE" without re-running.
    last_run_summary: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Free-form labels (["baseline", "optimized", "what-if"]) for filtering.
    tags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Soft delete
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    # Audit
    created_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<SimulationScenario(id={self.id}, name={self.name!r}, client={self.client_id})>"
