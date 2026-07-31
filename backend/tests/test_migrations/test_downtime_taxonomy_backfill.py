"""Runs alembic upgrade against a temp SQLite DB seeded with legacy rows.

Follows the existing migration-test approach in backend/tests/ (see the
baseline-equality test in test_mariadb_portability.py) for building an
alembic Config against a throwaway database URL.
"""

import sqlite3

import pytest
from alembic import command
from alembic.config import Config

LEGACY_ROWS = [
    # (id, reason, category, notes)
    ("DT-L-1", "CHANGEOVER", None, None),  # rogue reason -> SETUP_CHANGEOVER, cat from mapping -> scheduling
    ("DT-L-2", "PLANNED_MAINTENANCE", "Maintenance", None),  # rogue reason -> MAINTENANCE; category text -> machine
    ("DT-L-3", "EQUIPMENT_FAILURE", "Breakdown", None),  # phantom category -> machine
    ("DT-L-4", "OTHER", "weird stuff", "keep me"),  # unknown -> uncategorized + notes preserved
    ("DT-L-5", "MATERIAL_SHORTAGE", None, None),  # NULL -> materials (mapping)
    ("DT-L-6", "QUALITY_HOLD", "other", None),  # already valid -> unchanged
    ("DT-L-7", "TOTALLY_UNKNOWN", None, None),  # unknown reason -> OTHER + notes tag, cat -> other
]


@pytest.fixture()
def migrated_db(tmp_path):
    db_path = tmp_path / "mig.db"
    url = f"sqlite:///{db_path}"
    cfg = Config("alembic.ini")  # run pytest from backend/
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0001_baseline")

    conn = sqlite3.connect(db_path)
    # CLIENT has two more NOT NULL columns with no server default beyond
    # client_id/client_name: client_type (Enum) and is_active (Integer).
    # Confirmed via PRAGMA table_info(CLIENT) against the 0001 baseline.
    conn.execute(
        "INSERT INTO CLIENT (client_id, client_name, client_type, is_active)" " VALUES ('C1', 'Test', 'Other', 1)"
    )
    for rid, reason, category, notes in LEGACY_ROWS:
        conn.execute(
            "INSERT INTO DOWNTIME_ENTRY (downtime_entry_id, client_id, shift_date,"
            " downtime_reason, downtime_duration_minutes, root_cause_category, notes)"
            " VALUES (?, 'C1', '2026-07-01 06:00:00', ?, 30, ?, ?)",
            (rid, reason, category, notes),
        )
    conn.commit()
    conn.close()

    command.upgrade(cfg, "0002_downtime_taxonomy")
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


def _row(conn, rid):
    cur = conn.execute(
        "SELECT downtime_reason, root_cause_category, notes FROM DOWNTIME_ENTRY WHERE downtime_entry_id=?",
        (rid,),
    )
    return cur.fetchone()


def test_rogue_reasons_normalized(migrated_db):
    assert _row(migrated_db, "DT-L-1")[0] == "SETUP_CHANGEOVER"
    assert _row(migrated_db, "DT-L-2")[0] == "MAINTENANCE"


def test_unknown_reason_becomes_other_with_notes_tag(migrated_db):
    reason, _, notes = _row(migrated_db, "DT-L-7")
    assert reason == "OTHER"
    assert "[legacy reason: TOTALLY_UNKNOWN]" in (notes or "")


def test_phantom_and_text_categories_mapped(migrated_db):
    assert _row(migrated_db, "DT-L-3")[1] == "machine"
    assert _row(migrated_db, "DT-L-2")[1] == "machine"


def test_null_category_backfilled_from_normalized_reason(migrated_db):
    assert _row(migrated_db, "DT-L-1")[1] == "scheduling"
    assert _row(migrated_db, "DT-L-5")[1] == "materials"


def test_unknown_category_becomes_uncategorized_and_preserves_original_in_notes(migrated_db):
    _, category, notes = _row(migrated_db, "DT-L-4")
    assert category == "uncategorized"
    assert "[legacy category: weird stuff]" in notes
    assert "keep me" in notes


def test_already_valid_category_unchanged(migrated_db):
    assert _row(migrated_db, "DT-L-6")[1] == "other"


def test_no_nulls_remain(migrated_db):
    cur = migrated_db.execute("SELECT COUNT(*) FROM DOWNTIME_ENTRY WHERE root_cause_category IS NULL")
    assert cur.fetchone()[0] == 0
