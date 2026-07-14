"""
Simulation-scenario builder for the demo-client seeder.

No behavior change from the pre-split version — this is a pure move.
"""

from sqlalchemy.orm import Session


def seed_simulation(session: Session, client_id: str) -> None:
    """Idempotent per-client baseline SimulationScenario. config_json is a
    minimal, schema-valid SimulationConfig.model_dump() (one operation, one
    demand, one shift schedule) — the engine only needs a structurally valid
    payload for the demo Save/Load list, not a rich what-if scenario."""
    from backend.orm.simulation_scenario import SimulationScenario

    if session.query(SimulationScenario).filter_by(client_id=client_id).first() is not None:
        return
    from backend.simulation_v2.models import SimulationConfig, OperationInput, ScheduleConfig, DemandInput, DemandMode

    config = SimulationConfig(
        operations=[
            OperationInput(
                product=f"{client_id}-P1",
                step=1,
                operation="Sew seams",
                machine_tool="Overlock 4-thread",
                sam_min=2.5,
            )
        ],
        schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5),
        demands=[DemandInput(product=f"{client_id}-P1", bundle_size=10, daily_demand=500)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    ).model_dump(mode="json")
    session.add(
        SimulationScenario(
            name=f"{client_id} Baseline Scenario",
            client_id=client_id,
            config_json=config,
            description="Seeded baseline what-if scenario",
            is_active=True,
        )
    )
    session.flush()
