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
