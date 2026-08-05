"""Cycle 3 PR-A DDL — same throwaway-SQLite alembic harness as its siblings."""

import sqlite3

import pytest
from alembic import command
from alembic.config import Config

ATT_COLUMNS = {"normal_hours", "double_hours", "triple_hours", "labor_class_override"}


@pytest.fixture()
def upgraded_db(tmp_path):
    db_path = tmp_path / "mig4.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    yield conn, cfg, db_path
    conn.close()


def _cols(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_upgrade_adds_attendance_columns(upgraded_db):
    conn, _, _ = upgraded_db
    assert ATT_COLUMNS <= _cols(conn, "ATTENDANCE_ENTRY")


def test_upgrade_adds_employee_column(upgraded_db):
    conn, _, _ = upgraded_db
    assert "labor_class" in _cols(conn, "EMPLOYEE")


def test_upgrade_creates_allocation_table_with_unique(upgraded_db):
    conn, _, _ = upgraded_db
    assert _cols(conn, "ATTENDANCE_HOUR_ALLOCATION") == {
        "allocation_id",
        "attendance_entry_id",
        "category",
        "hours",
    }
    indexes = conn.execute("PRAGMA index_list(ATTENDANCE_HOUR_ALLOCATION)").fetchall()
    assert any(row[2] == 1 for row in indexes), "expected a UNIQUE index on (entry, category)"


def test_head_is_0004(upgraded_db):
    conn, _, _ = upgraded_db
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004_labor_hours"


def test_downgrade_removes_everything(upgraded_db):
    conn, cfg, db_path = upgraded_db
    conn.close()
    command.downgrade(cfg, "0003_justified_delay")
    conn2 = sqlite3.connect(db_path)
    try:
        assert not (ATT_COLUMNS & _cols(conn2, "ATTENDANCE_ENTRY"))
        assert "labor_class" not in _cols(conn2, "EMPLOYEE")
        tables = {r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "ATTENDANCE_HOUR_ALLOCATION" not in tables
    finally:
        conn2.close()
