"""
Capacity Scenario - What-if scenario configurations
Stores scenario parameters and results for capacity planning simulations.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy import DateTime
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
        Index('ix_capacity_scenario_base', 'client_id', 'base_schedule_id'),
        Index('ix_capacity_scenario_type', 'client_id', 'scenario_type'),
        {"extend_existing": True}
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Scenario identification (scenario_type indexed via composite index in __table_args__)
    scenario_name = Column(String(100), nullable=False)
    scenario_type = Column(String(50), nullable=True)

    # Base schedule this scenario modifies (indexed via composite index in __table_args__)
    base_schedule_id = Column(Integer, ForeignKey("capacity_schedule.id"), nullable=True)

    # Scenario parameters stored as JSON
    # Example structures by type:
    # OVERTIME: {"overtime_percent": 20, "affected_lines": ["LINE1", "LINE2"], "days": ["MON", "TUE"]}
    # SETUP_REDUCTION: {"reduction_percent": 15, "affected_operations": ["OP1", "OP2"]}
    # SUBCONTRACT: {"quantity": 1000, "style_code": "STYLE1", "cost_per_unit": 5.50}
    # SHIFT_ADD: {"shift_number": 2, "hours": 8, "affected_lines": ["LINE1"]}
    # EFFICIENCY_IMPROVEMENT: {"target_efficiency": 90, "investment_cost": 10000}
    # LABOR_ADD: {"operators": 5, "affected_lines": ["LINE1", "LINE2"], "cost_per_operator": 150}
    parameters_json = Column(JSON, nullable=True)

    # Results stored as JSON
    # Example: {
    #   "original_capacity_hours": 400,
    #   "new_capacity_hours": 480,
    #   "capacity_increase_percent": 20,
    #   "cost_impact": 5000,
    #   "utilization_before": 95,
    #   "utilization_after": 79,
    #   "bottlenecks_resolved": ["LINE1"]
    # }
    results_json = Column(JSON, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

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
