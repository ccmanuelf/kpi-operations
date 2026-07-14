"""
Prod-safe demo-client seeder. INSERT-only; refuses any client not on a fixed
allowlist; never creates/drops schema (Alembic is the single schema mechanism).

Populates DEMO clients with a full, credible dataset (master data, config/catalog
layer, capacity planning-scheduling graph, work-order/workflow/hold variety, daily
Operations data, a simulation scenario) so the app can be validated as a real user.

VM invocation:
  docker compose -f docker-compose.prod.yml exec backend \\
      python -m backend.scripts.seed_sample_client --days 90
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse  # noqa: E402
from datetime import date  # noqa: E402
from typing import TYPE_CHECKING, Optional  # noqa: E402

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.exc import ArgumentError, NoSuchModuleError, OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.orm.client import Client, ClientType  # noqa: E402

from backend.scripts._seed_sections import (  # noqa: E402,F401 — rng_for re-exported for `seed.rng_for`
    rng_for,
    ClientSpec,
    seed_catalogs,
    seed_config_layer,
    seed_shifts,
    seed_products,
    seed_lines,
    seed_employees,
    seed_break_times,
    seed_equipment,
    seed_alerts,
    seed_capacity_graph,
    seed_work_orders,
    seed_holds,
    seed_daily_data,
    seed_simulation,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine  # noqa: E402


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


ALLOWLIST = frozenset({"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"})
DEFAULT_CLIENTS = ("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID")


CLIENT_SPECS: dict[str, ClientSpec] = {
    "DEMO-PIECE": ClientSpec("DEMO-PIECE", "Demo Piece-Rate Garments", ClientType.PIECE_RATE, 8, 8),
    "DEMO-HOURLY": ClientSpec("DEMO-HOURLY", "Demo Hourly Assembly", ClientType.HOURLY_RATE, 8, 8),
    "DEMO-HYBRID": ClientSpec("DEMO-HYBRID", "Demo Hybrid Works", ClientType.HYBRID, 8, 8),
    "SAMPLE_REF": ClientSpec("SAMPLE_REF", "SAMPLE_REF", ClientType.PIECE_RATE, 8, 8),
}


def ensure_migrated(engine: "Engine") -> None:
    """Refuse to touch a database Alembic hasn't built (never creates schema)."""
    insp = inspect(engine)
    if not (insp.has_table("alembic_version") and insp.has_table("CLIENT") and insp.has_table("USER")):
        raise SeedError(
            "database is not migrated (alembic_version/CLIENT/USER missing). "
            "Start the backend once (its entrypoint runs `alembic upgrade head`), then retry."
        )


def resolve_entered_by(session: Session, client_id: str) -> str:
    """Resolve a real USER.user_id for entered_by/inspector_id: prefer a
    client-scoped operator, else any admin. No users are created."""
    from backend.orm.user import User

    # client_id_assigned is a comma-separated list; .contains() is only a coarse,
    # index-friendly prefilter — refine with EXACT element membership so a
    # superstring client id (e.g. "DEMO-PIECE-2") can't mis-match "DEMO-PIECE".
    candidates = (
        session.query(User)
        .filter(User.client_id_assigned.isnot(None), User.client_id_assigned.contains(client_id))
        .all()
    )
    for user in candidates:
        assigned = [c.strip() for c in (user.client_id_assigned or "").split(",")]
        if client_id in assigned:
            return user.user_id
    admin = session.query(User).filter(User.role == "admin").first()
    if admin is not None:
        return admin.user_id
    raise SeedError(f"no usable entered_by user for {client_id} (need a client operator or an admin).")


def seed_client_row(session: Session, spec: ClientSpec) -> None:
    """Idempotent CLIENT insert."""
    if session.get(Client, spec.client_id) is not None:
        return
    session.add(
        Client(
            client_id=spec.client_id,
            client_name=spec.client_name,
            client_type=spec.client_type,
            is_active=1,
        )
    )
    session.flush()


# Children-first ordered (ORM class, client-column) list for scoped reset.
# Completed here so reset is correct as later tasks bring tables online
# (deleting zero rows for a not-yet-seeded table is harmless). NEVER includes CLIENT.
def _reset_table_order() -> list[tuple[type, str]]:
    from backend.orm import (
        AttendanceEntry,
        DefectDetail,
        DowntimeEntry,
        HoldEntry,
        Job,
        ProductionEntry,
        QualityEntry,
        Shift,
        Product,
        WorkOrder,
        WorkflowTransitionLog,
    )
    from backend.orm.employee import Employee
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from backend.orm.employee_client_assignment import EmployeeClientAssignment
    from backend.orm.floating_pool import FloatingPool
    from backend.orm.production_line import ProductionLine
    from backend.orm.equipment import Equipment
    from backend.orm.break_time import BreakTime
    from backend.orm.alert import Alert
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    from backend.orm.simulation_scenario import SimulationScenario
    from backend.orm.capacity import (
        CapacityKPICommitment,
        CapacityScheduleDetail,
        CapacitySchedule,
        CapacityComponentCheck,
        CapacityAnalysis,
        CapacityStockSnapshot,
        CapacityBOMDetail,
        CapacityBOMHeader,
        CapacityProductionStandard,
        CapacityOrder,
        CapacityScenario,
        CapacityCalendar,
        CapacityProductionLine,
    )

    return [
        (DefectDetail, "client_id_fk"),
        (QualityEntry, "client_id"),
        (ProductionEntry, "client_id"),
        (DowntimeEntry, "client_id"),
        (AttendanceEntry, "client_id"),
        (WorkflowTransitionLog, "client_id"),
        (HoldEntry, "client_id"),
        (Job, "client_id_fk"),
        (Alert, "client_id"),  # child of WorkOrder (work_order_id, nullable FK)
        (WorkOrder, "client_id"),
        (CapacityKPICommitment, "client_id"),  # child of CapacitySchedule
        (CapacityScheduleDetail, "client_id"),  # child of CapacitySchedule, CapacityOrder, CapacityProductionLine
        (CapacityScenario, "client_id"),  # child of CapacitySchedule
        (CapacitySchedule, "client_id"),
        (CapacityComponentCheck, "client_id"),  # child of CapacityOrder
        (CapacityAnalysis, "client_id"),  # child of CapacityProductionLine
        (CapacityStockSnapshot, "client_id"),
        (CapacityBOMDetail, "client_id"),  # child of CapacityBOMHeader
        (CapacityBOMHeader, "client_id"),
        (CapacityProductionStandard, "client_id"),
        (CapacityOrder, "client_id"),
        (CapacityCalendar, "client_id"),
        (EmployeeLineAssignment, "client_id"),  # child of ProductionLine, Employee
        (EmployeeClientAssignment, "client_id"),  # child of Employee
        (FloatingPool, "client_id"),  # child of Employee
        (Employee, "client_id_assigned"),
        (BreakTime, "client_id"),  # child of Shift
        (Shift, "client_id"),  # child of ProductionLine (line_id, nullable)
        (Product, "client_id"),
        (Equipment, "client_id"),  # child of ProductionLine
        (ProductionLine, "client_id"),  # child of CapacityProductionLine
        (CapacityProductionLine, "client_id"),
        (SimulationScenario, "client_id"),
        (AlertConfig, "client_id"),
        (KPIThreshold, "client_id"),
        (ClientConfig, "client_id"),
        (HoldStatusCatalog, "client_id"),
        (HoldReasonCatalog, "client_id"),
        (DefectTypeCatalog, "client_id"),
    ]


RESET_TABLE_ORDER = _reset_table_order()


def reset_client_data(session: Session, client_id: str) -> None:
    """Delete ONLY this client's rows, children-first. Leaves CLIENT + other clients intact."""
    for cls, col in RESET_TABLE_ORDER:
        session.query(cls).filter(getattr(cls, col) == client_id).delete(synchronize_session=False)
    session.flush()


def seed_client(session: Session, spec: ClientSpec, days: int, anchor: date) -> None:
    """Orchestrator — seed one client in FK order: catalogs/config → master
    data → capacity → work orders → holds → daily data → simulation."""
    seed_client_row(session, spec)
    seed_catalogs(session, spec.client_id)
    seed_config_layer(session, spec.client_id)
    seed_shifts(session, spec.client_id)
    seed_products(session, spec.client_id)
    seed_lines(session, spec.client_id)
    seed_employees(session, spec)
    seed_break_times(session, spec.client_id)
    seed_equipment(session, spec.client_id)
    seed_alerts(session, spec.client_id)
    seed_capacity_graph(session, spec.client_id, days, anchor)
    entered_by = resolve_entered_by(session, spec.client_id)
    work_orders = seed_work_orders(session, spec, entered_by, anchor)
    seed_holds(session, spec.client_id, work_orders, entered_by, anchor)
    seed_daily_data(session, spec, days, entered_by, anchor)
    seed_simulation(session, spec.client_id)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seed_sample_client",
        description="Seed DEMO clients with a full credible dataset (INSERT-only, allowlist-guarded).",
    )
    parser.add_argument("--client", default=None, help=f"one of {sorted(ALLOWLIST)}; default = the 3 DEMO-* clients")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="working days of daily Operations data (default 90; weekends skipped)",
    )
    parser.add_argument("--reset", action="store_true", help="delete this client's existing rows before seeding")
    parser.add_argument(
        "--anchor",
        default=None,
        help=(
            "YYYY-MM-DD anchor for seeded dates (Operations history ends here, "
            "capacity planning starts here); default = today"
        ),
    )
    args = parser.parse_args(argv)

    if args.client is not None and args.client not in ALLOWLIST:
        print(f"ERROR: {args.client!r} is not on the demo allowlist {sorted(ALLOWLIST)}; refusing.", file=sys.stderr)
        return 1
    targets = [args.client] if args.client else list(DEFAULT_CLIENTS)

    try:
        anchor = date.fromisoformat(args.anchor) if args.anchor else date.today()
    except ValueError:
        print(f"ERROR: --anchor {args.anchor!r} is not a valid YYYY-MM-DD date.", file=sys.stderr)
        return 1

    database_url = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")
    try:
        engine = create_engine(database_url)
    except (ArgumentError, NoSuchModuleError):
        print(
            "ERROR: invalid DATABASE_URL (unparseable URL or unknown dialect); check the environment/.env.",
            file=sys.stderr,
        )
        return 1

    try:
        ensure_migrated(engine)
        with Session(engine) as session:
            for client_id in targets:
                spec = CLIENT_SPECS[client_id]
                if args.reset:
                    reset_client_data(session, client_id)
                seed_client(session, spec, args.days, anchor)
                session.commit()
                print(f"Seeded {client_id} ({args.days} days).")
    except SeedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(f"ERROR: database unreachable: {exc.orig}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
