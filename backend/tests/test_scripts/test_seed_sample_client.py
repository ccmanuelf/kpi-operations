from pathlib import Path

import pytest

from backend.orm import Client
from backend.orm.client import ClientType
from backend.scripts import seed_sample_client as seed

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_SRC = (REPO_ROOT / "backend/scripts/seed_sample_client.py").read_text(encoding="utf-8")


def test_allowlist_is_exactly_the_demo_clients():
    assert seed.ALLOWLIST == frozenset({"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"})
    assert set(seed.DEFAULT_CLIENTS) == {"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID"}


def test_prod_safety_static_scan():
    # The script must never be able to drop/create schema or gate on DEMO_MODE.
    for forbidden in ("drop_all", "create_all", "rebuild_schema", "DEMO_MODE"):
        assert forbidden not in SCRIPT_SRC, f"forbidden token {forbidden!r} present in seed script"


def test_main_refuses_non_allowlist_client(capsys):
    rc = seed.main(["--client", "REAL-PROD-CLIENT"])
    assert rc == 1
    assert "allowlist" in capsys.readouterr().err.lower()


def test_ensure_migrated_rejects_empty_db(tmp_path):
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path/'empty.db'}")
    try:
        with pytest.raises(seed.SeedError):
            seed.ensure_migrated(engine)
    finally:
        engine.dispose()


def test_rng_is_deterministic_across_calls():
    a = [seed.rng_for("DEMO-PIECE", "prod", 3).random() for _ in range(1)]
    b = [seed.rng_for("DEMO-PIECE", "prod", 3).random() for _ in range(1)]
    assert a == b
    assert seed.rng_for("DEMO-PIECE", "prod", 3).random() != seed.rng_for("DEMO-HOURLY", "prod", 3).random()


def test_seed_client_row_idempotent(db_session):
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    seed.seed_client_row(db_session, spec)  # second call must be a no-op
    db_session.commit()
    rows = db_session.query(Client).filter(Client.client_id == "DEMO-PIECE").all()
    assert len(rows) == 1
    assert rows[0].client_type == ClientType.PIECE_RATE
    assert rows[0].client_name == spec.client_name


def test_reset_table_order_children_before_parents():
    # (parent_class_name, child_class_name) FK edges within RESET_TABLE_ORDER;
    # each child must be deleted BEFORE its parent (children-first) or MariaDB --reset FK-violates.
    order = [cls.__name__ for cls, _ in seed.RESET_TABLE_ORDER]
    edges = [
        ("QualityEntry", "DefectDetail"),
        ("WorkOrder", "Job"),
        ("WorkOrder", "HoldEntry"),
        ("WorkOrder", "WorkflowTransitionLog"),
        ("WorkOrder", "QualityEntry"),
        ("WorkOrder", "ProductionEntry"),
        ("CapacitySchedule", "CapacityKPICommitment"),
        ("CapacitySchedule", "CapacityScheduleDetail"),
        ("CapacitySchedule", "CapacityScenario"),
        ("CapacityOrder", "CapacityComponentCheck"),
        ("CapacityOrder", "CapacityScheduleDetail"),
        ("CapacityProductionLine", "CapacityScheduleDetail"),
        ("CapacityProductionLine", "CapacityAnalysis"),
        ("CapacityProductionLine", "ProductionLine"),
        ("CapacityBOMHeader", "CapacityBOMDetail"),
        ("Employee", "EmployeeLineAssignment"),
        ("Employee", "EmployeeClientAssignment"),
        ("ProductionLine", "EmployeeLineAssignment"),
        ("ProductionLine", "Shift"),
    ]
    for parent, child in edges:
        assert parent in order and child in order, f"{parent}/{child} missing from RESET_TABLE_ORDER"
        assert order.index(child) < order.index(parent), f"{child} must be deleted before {parent}"
    assert "CLIENT" not in order and "Client" not in order  # CLIENT row is never deleted


def test_catalogs_and_config_seeded_and_idempotent(db_session):
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    for _ in range(2):  # idempotent
        seed.seed_catalogs(db_session, "DEMO-PIECE")
        seed.seed_config_layer(db_session, "DEMO-PIECE")
    db_session.commit()

    cid = "DEMO-PIECE"
    assert db_session.query(HoldStatusCatalog).filter_by(client_id=cid).count() == 7
    assert db_session.query(HoldReasonCatalog).filter_by(client_id=cid).count() >= 6
    assert db_session.query(DefectTypeCatalog).filter_by(client_id=cid).count() >= 5
    assert db_session.query(ClientConfig).filter_by(client_id=cid).count() == 1
    assert db_session.query(KPIThreshold).filter_by(client_id=cid).count() >= 6
    assert db_session.query(AlertConfig).filter_by(client_id=cid).count() >= 3


def test_defect_catalog_pk_is_client_scoped_no_collision(db_session):
    from backend.db.factories import TestDataFactory
    from backend.orm.defect_type_catalog import DefectTypeCatalog

    for cid in ("DEMO-PIECE", "DEMO-HOURLY"):
        seed.seed_client_row(db_session, seed.CLIENT_SPECS[cid])
    seed.seed_catalogs(db_session, "DEMO-PIECE")
    db_session.commit()
    TestDataFactory.reset_counters()  # simulate a fresh process (counter restarts at 1)
    seed.seed_catalogs(db_session, "DEMO-HOURLY")  # must NOT raise IntegrityError
    db_session.commit()

    ids = [r.defect_type_id for r in db_session.query(DefectTypeCatalog).all()]
    assert len(ids) == len(set(ids)), "defect_type_id PKs collide across clients"
    for r in db_session.query(DefectTypeCatalog).all():
        assert r.client_id in r.defect_type_id, "defect_type_id must be client-scoped"


def test_master_data_seeded_and_idempotent(db_session):
    from backend.orm import Shift, Product
    from backend.orm.employee import Employee
    from backend.orm.production_line import ProductionLine
    from backend.orm.employee_client_assignment import EmployeeClientAssignment
    from backend.orm.employee_line_assignment import EmployeeLineAssignment

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    for _ in range(2):
        seed.seed_shifts(db_session, spec.client_id)
        seed.seed_products(db_session, spec.client_id)
        seed.seed_lines(db_session, spec.client_id)
        seed.seed_employees(db_session, spec)
    db_session.commit()

    cid = "DEMO-PIECE"
    assert db_session.query(Shift).filter_by(client_id=cid).count() == 2
    assert db_session.query(Product).filter_by(client_id=cid).count() == 3
    assert db_session.query(ProductionLine).filter_by(client_id=cid).count() == 2
    assert db_session.query(Employee).filter_by(client_id_assigned=cid).count() == spec.num_employees
    assert db_session.query(EmployeeClientAssignment).filter_by(client_id=cid).count() == spec.num_employees
    assert db_session.query(EmployeeLineAssignment).filter_by(client_id=cid).count() >= spec.num_employees


def test_employee_codes_unique_across_demo_clients(db_session):
    from backend.orm.employee import Employee

    # DEMO-HOURLY and DEMO-HYBRID both used to map to prefix "DH" -> employee_code collision.
    for cid in ("DEMO-HOURLY", "DEMO-HYBRID"):
        spec = seed.CLIENT_SPECS[cid]
        seed.seed_client_row(db_session, spec)
        seed.seed_shifts(db_session, cid)
        seed.seed_products(db_session, cid)
        seed.seed_lines(db_session, cid)
        seed.seed_employees(db_session, spec)  # 2nd client must NOT IntegrityError
    db_session.commit()

    codes = [e.employee_code for e in db_session.query(Employee).all()]
    assert len(codes) == len(set(codes)), "employee_code collides across clients"
    for e in db_session.query(Employee).all():
        assert e.client_id_assigned in e.employee_code, "employee_code must be client-scoped"


def test_capacity_graph_seeded_and_idempotent(db_session):
    from backend.orm.capacity import (
        CapacityCalendar,
        CapacityOrder,
        CapacityProductionStandard,
        CapacityBOMHeader,
        CapacityStockSnapshot,
        CapacityComponentCheck,
        CapacitySchedule,
        CapacityScheduleDetail,
        CapacityKPICommitment,
        CapacityScenario,
        CapacityAnalysis,
    )
    from backend.orm.capacity.orders import OrderStatus

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    seed.seed_lines(db_session, spec.client_id)
    for _ in range(2):
        seed.seed_capacity_graph(db_session, spec.client_id, days=30)
    db_session.commit()

    cid = "DEMO-PIECE"
    assert db_session.query(CapacityCalendar).filter_by(client_id=cid).count() >= 30
    orders = db_session.query(CapacityOrder).filter_by(client_id=cid).all()
    assert len(orders) >= 5
    statuses = {o.status for o in orders}
    assert OrderStatus.COMPLETED in statuses and OrderStatus.CANCELLED in statuses
    assert db_session.query(CapacityProductionStandard).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityBOMHeader).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityStockSnapshot).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityComponentCheck).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacitySchedule).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityScheduleDetail).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityKPICommitment).filter_by(client_id=cid).count() >= 1

    scenarios = db_session.query(CapacityScenario).filter_by(client_id=cid).all()
    assert len(scenarios) == 1
    assert cid in scenarios[0].scenario_name

    analyses = db_session.query(CapacityAnalysis).filter_by(client_id=cid).all()
    assert len(analyses) >= 1


def _seed_admin(db_session):
    from backend.db.factories import TestDataFactory
    from backend.orm import User

    if db_session.query(User).filter_by(role="admin").first() is None:
        TestDataFactory.create_user(db_session, username="seed_admin", role="admin")
        db_session.flush()


def test_work_orders_cover_all_statuses_with_transitions_and_holds(db_session):
    from backend.orm import WorkOrder, WorkOrderStatus, WorkflowTransitionLog, HoldEntry, Job

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10)  # full orchestrator so entered_by resolves
    db_session.commit()

    cid = "DEMO-PIECE"
    wos = db_session.query(WorkOrder).filter_by(client_id=cid).all()
    present = {wo.status for wo in wos}
    required = {
        WorkOrderStatus.RECEIVED,
        WorkOrderStatus.RELEASED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.SHIPPED,
        WorkOrderStatus.CLOSED,
        WorkOrderStatus.CANCELLED,
        WorkOrderStatus.ON_HOLD,
    }
    assert required.issubset(present), f"missing statuses: {required - present}"
    assert db_session.query(WorkflowTransitionLog).filter_by(client_id=cid).count() >= len(wos)
    assert db_session.query(Job).filter_by(client_id_fk=cid).count() >= 1

    holds = db_session.query(HoldEntry).filter_by(client_id=cid).all()
    hold_statuses = {h.hold_status for h in holds}
    for expected in (
        "PENDING_HOLD_APPROVAL",
        "ON_HOLD",
        "PENDING_RESUME_APPROVAL",
        "RESUMED",
        "RELEASED",
        "CANCELLED",
        "SCRAPPED",
    ):
        assert expected in hold_statuses, f"missing hold status {expected}"


def test_daily_data_scales_with_days_and_is_credible(db_session):
    from decimal import Decimal  # noqa: F401
    from backend.orm import ProductionEntry, QualityEntry, DowntimeEntry, AttendanceEntry, DefectDetail

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=20)
    db_session.commit()

    cid = "DEMO-PIECE"
    prod = db_session.query(ProductionEntry).filter_by(client_id=cid).all()
    assert len(prod) >= 20  # at least one per working span day
    for pe in prod:
        assert pe.units_produced > 0
        assert pe.run_time_hours > 0
        assert pe.employees_assigned > 0
        assert pe.defect_count >= 0 and pe.scrap_count >= 0
        assert pe.defect_count <= pe.units_produced
    assert db_session.query(QualityEntry).filter_by(client_id=cid).count() >= 20
    assert db_session.query(DefectDetail).filter_by(client_id_fk=cid).count() >= 1
    assert db_session.query(DowntimeEntry).filter_by(client_id=cid).count() >= 1
    assert db_session.query(AttendanceEntry).filter_by(client_id=cid).count() >= 20

    # quality math is internally consistent (credibility)
    for qe in db_session.query(QualityEntry).filter_by(client_id=cid).all():
        assert qe.units_passed + qe.units_defective == qe.units_inspected
        assert 0 <= qe.units_defective <= qe.units_inspected


def test_simulation_scenario_seeded(db_session):
    from backend.orm.simulation_scenario import SimulationScenario

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=5)
    db_session.commit()
    scenarios = db_session.query(SimulationScenario).filter_by(client_id="DEMO-PIECE").all()
    assert len(scenarios) == 1
    assert scenarios[0].config_json is not None
    assert scenarios[0].is_active is True


def test_full_seed_is_idempotent(db_session):
    from backend.orm import ProductionEntry

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10)
    db_session.commit()
    before = db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count()
    seed.seed_client(db_session, spec, days=10)  # second full run
    db_session.commit()
    after = db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count()
    assert after == before  # zero new rows


def test_reset_removes_only_target_client(db_session):
    from backend.orm import ProductionEntry, Client

    _seed_admin(db_session)
    piece = seed.CLIENT_SPECS["DEMO-PIECE"]
    hourly = seed.CLIENT_SPECS["DEMO-HOURLY"]
    seed.seed_client(db_session, piece, days=6)
    seed.seed_client(db_session, hourly, days=6)
    db_session.commit()

    seed.reset_client_data(db_session, "DEMO-PIECE")
    db_session.commit()
    assert db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count() == 0
    assert db_session.query(ProductionEntry).filter_by(client_id="DEMO-HOURLY").count() > 0
    assert db_session.get(Client, "DEMO-PIECE") is not None  # CLIENT row kept


def test_cli_smoke_seeds_and_reports(tmp_path, monkeypatch, capsys):
    from backend.db.migrate import upgrade_to_head
    from backend.db.factories import TestDataFactory
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SASession
    from backend.orm import ProductionEntry

    db_file = tmp_path / "cli.db"
    url = f"sqlite:///{db_file}"
    upgrade_to_head(url)
    eng = create_engine(url)
    with SASession(eng) as s:  # need an admin for entered_by
        TestDataFactory.create_user(s, username="cli_admin", role="admin")
        s.commit()
    eng.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    rc = seed.main(["--client", "DEMO-PIECE", "--days", "8"])
    assert rc == 0
    assert "Seeded DEMO-PIECE" in capsys.readouterr().out

    eng = create_engine(url)
    with SASession(eng) as s:
        assert s.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count() > 0
    eng.dispose()


def test_daily_data_pks_client_scoped_no_cross_process_collision(db_session):
    # Reproduces the process-local-counter PK-collision class deterministically:
    # seed one client, reset the factory counters (= a fresh process), seed another;
    # deterministic client-scoped PKs must not collide.
    from backend.db.factories import TestDataFactory
    from backend.orm import ProductionEntry, AttendanceEntry, QualityEntry

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=8)
    db_session.commit()
    TestDataFactory.reset_counters()
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-HOURLY"], days=8)  # must NOT IntegrityError
    db_session.commit()

    for model, pk in (
        (ProductionEntry, "production_entry_id"),
        (AttendanceEntry, "attendance_entry_id"),
        (QualityEntry, "quality_entry_id"),
    ):
        rows = db_session.query(model).all()
        ids = [getattr(r, pk) for r in rows]
        assert len(ids) == len(set(ids)), f"{pk} collides across clients"
        for r in rows:
            owner = getattr(r, "client_id", None) or getattr(r, "client_id_fk", None)
            assert owner in getattr(r, pk), f"{pk} must be client-scoped"


def test_seeder_uses_no_wall_clock():
    # All seeded dates derive from ANCHOR_DATE; no date.today()/datetime.now()/utcnow()
    # anywhere, so the dataset is byte-identical regardless of when the seeder runs.
    import re

    for forbidden in (r"date\.today\(", r"datetime\.now\(", r"utcnow\("):
        assert not re.search(forbidden, SCRIPT_SRC), f"wall-clock call {forbidden!r} breaks seed determinism"


def test_resolve_entered_by_exact_client_membership(db_session):
    # .contains() is a coarse prefilter; resolution must match the client_id as an
    # EXACT comma-list element, so a superstring-assigned user is NOT mis-selected.
    from backend.db.factories import TestDataFactory
    from backend.orm import Client
    from backend.orm.client import ClientType

    db_session.add(Client(client_id="DEMO-PIECE", client_name="P", client_type=ClientType.PIECE_RATE, is_active=1))
    db_session.add(Client(client_id="DEMO-PIECE-2", client_name="P2", client_type=ClientType.PIECE_RATE, is_active=1))
    db_session.flush()
    TestDataFactory.create_user(db_session, username="superstring_op", role="operator", client_id="DEMO-PIECE-2")
    admin = TestDataFactory.create_user(db_session, username="fallback_admin", role="admin")
    db_session.flush()
    # No exact DEMO-PIECE user exists → must fall back to admin, NOT the DEMO-PIECE-2 operator.
    assert seed.resolve_entered_by(db_session, "DEMO-PIECE") == admin.user_id

    exact = TestDataFactory.create_user(db_session, username="exact_op", role="operator", client_id="DEMO-PIECE")
    db_session.flush()
    assert seed.resolve_entered_by(db_session, "DEMO-PIECE") == exact.user_id
