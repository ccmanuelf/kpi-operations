"""First DDL revision since the baseline — verify columns appear on upgrade.

Same throwaway-SQLite alembic harness as test_downtime_taxonomy_backfill.py.
"""

import sqlite3

import pytest
from alembic import command
from alembic.config import Config

NEW_COLUMNS = {"delay_classification", "justified_delay_reason", "delay_classification_note"}


@pytest.fixture()
def upgraded_db(tmp_path):
    db_path = tmp_path / "mig3.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "0003_justified_delay")
    conn = sqlite3.connect(db_path)
    yield conn, cfg, db_path
    conn.close()


def _wo_columns(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(WORK_ORDER)").fetchall()}


def test_upgrade_head_adds_the_three_columns(upgraded_db):
    conn, _, _ = upgraded_db
    assert NEW_COLUMNS <= _wo_columns(conn)


def test_head_is_0003(upgraded_db):
    conn, _, _ = upgraded_db
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003_justified_delay"


def test_downgrade_removes_the_columns(upgraded_db):
    conn, cfg, db_path = upgraded_db
    conn.close()
    command.downgrade(cfg, "0002_downtime_taxonomy")
    conn2 = sqlite3.connect(db_path)
    try:
        assert not (NEW_COLUMNS & _wo_columns(conn2))
    finally:
        conn2.close()
