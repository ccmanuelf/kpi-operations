"""
Capacity Scenario - What-if scenario configurations
Stores scenario parameters and results for capacity planning simulations.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CapacityScenario(Base):
    """
    CAPACITY_SCENARIO table - What-if scenario configurations

    Purpose:
    - Store scenario parameters for capacity simulations
    - Track results of what-if analyses
    - Link scenarios to base schedules

    Scenario Types:
    - OVERTIME: Add overtime hours
    - SETUP_REDUCTION: Reduce setup/changeover time
    - SUBCONTRACT: Outsource capacity
    - SHIFT_ADD: Add additional shifts
    - EFFICIENCY_IMPROVEMENT: Improve efficiency factors
    - LABOR_ADD: Add operators/workers

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_scenario"
    __table_args__ = (
        Index("ix_capacity_scenario_base", "client_id", "base_schedule_id"),
        Index("ix_capacity_scenario_type", "client_id", "scenario_type"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Scenario identification (scenario_type indexed via composite index in __table_args__)
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scenario_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Base schedule this scenario modifies (indexed via composite index in __table_args__)
    base_schedule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("capacity_schedule.id"), nullable=True)

    # Scenario parameters stored as JSON
    parameters_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Results stored as JSON
    results_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def get_parameter(self, key: str, default=None):
        """Get a parameter value from parameters_json."""
        if not self.parameters_json:
            return default
        return self.parameters_json.get(key, default)

    def get_result(self, key: str, default=None):
        """Get a result value from results_json."""
        if not self.results_json:
            return default
        return self.results_json.get(key, default)

    def capacity_increase_percent(self) -> float:
        """Get capacity increase percentage from results."""
        return self.get_result("capacity_increase_percent", 0.0)

    def cost_impact(self) -> float:
        """Get cost impact from results."""
        return self.get_result("cost_impact", 0.0)

    def __repr__(self):
        return f"<CapacityScenario(name={self.scenario_name}, type={self.scenario_type})>"
