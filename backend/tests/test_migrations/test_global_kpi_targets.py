"""0009 supplies global KPI target defaults without trampling configuration.

The generators now read targets from `KPI_THRESHOLD` rather than from literals,
which only works if the configuration exists. It did not: nothing in the
repository inserted a global (`client_id IS NULL`) row, so a fresh clone had none
while the VM had nine made by hand. The same report rendered differently on the
two environments for reasons absent from the source.

An administrator's configured value is theirs, so the migration inserts only
where a key has no global row. That makes it idempotent, and makes it a no-op on
a deployment that already carries the defaults.

Runs a real `alembic upgrade` against a throwaway SQLite database, following the
idiom in test_downtime_taxonomy_backfill.py.
"""

import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from backend.alembic.versions import (  # noqa: F401  (import path check: the module must be loadable)
    __name__ as _versions_pkg,
)

REVISION = "0009_global_kpi_targets"
PREVIOUS = "0008_coverage_active_uniqueness"

#: Every key the migration is responsible for, and the direction each declares.
#: Named here rather than imported so a change to DEFAULTS has to be made twice
#: -- deliberately, because silently dropping a key would otherwise go unnoticed.
EXPECTED = {
    "efficiency": "Y",
    "performance": "Y",
    "availability": "Y",
    "oee": "Y",
    "fpy": "Y",
    "otd": "Y",
    "ppm": "N",
    "absenteeism": "N",
}


def _config(db_path):
    cfg = Config("alembic.ini")  # run pytest from backend/
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _globals(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT kpi_key, target_value, warning_threshold, critical_threshold,"
            " unit, higher_is_better, threshold_id"
            " FROM KPI_THRESHOLD WHERE client_id IS NULL"
        ).fetchall()
    finally:
        conn.close()
    return {r[0]: r[1:] for r in rows}


@pytest.fixture()
def at_previous(tmp_path):
    """A database migrated to just before 0009."""
    db_path = tmp_path / "thr.db"
    command.upgrade(_config(db_path), PREVIOUS)
    assert _globals(db_path) == {}, "0008 should leave no global thresholds behind"
    return db_path


class TestAFreshDeployment:
    def test_every_expected_key_gets_a_global_default(self, at_previous):
        command.upgrade(_config(at_previous), REVISION)

        assert set(_globals(at_previous)) == set(EXPECTED)

    def test_each_default_carries_both_bands_and_a_direction(self, at_previous):
        # A target with no bands cannot escalate past "At Risk", so defaults
        # without them would leave the status column two-state everywhere.
        command.upgrade(_config(at_previous), REVISION)

        for key, row in _globals(at_previous).items():
            target, warning, critical, unit, higher, _id = row
            assert target is not None, key
            assert warning is not None, f"{key} has no warning band"
            assert critical is not None, f"{key} has no critical band"
            assert unit, key
            assert higher == EXPECTED[key], f"{key} direction is {higher}, expected {EXPECTED[key]}"

    def test_the_bands_ascend_for_a_lower_is_better_metric(self, at_previous):
        # PPM and absenteeism get worse as they rise, so warning and critical sit
        # ABOVE target. Getting this backwards would make a breach unreachable.
        command.upgrade(_config(at_previous), REVISION)
        rows = _globals(at_previous)

        for key in ("ppm", "absenteeism"):
            target, warning, critical, _unit, higher, _id = rows[key]
            assert higher == "N", key
            assert target < warning < critical, f"{key}: {target} / {warning} / {critical}"

    def test_the_bands_descend_for_a_higher_is_better_metric(self, at_previous):
        command.upgrade(_config(at_previous), REVISION)
        rows = _globals(at_previous)

        for key, (target, warning, critical, _unit, higher, _id) in rows.items():
            if higher != "Y":
                continue
            assert target > warning > critical, f"{key}: {target} / {warning} / {critical}"


class TestAnExistingDeployment:
    def test_a_configured_global_value_is_not_overwritten(self, at_previous):
        # What the VM looks like: someone already set these by hand.
        conn = sqlite3.connect(at_previous)
        conn.execute(
            "INSERT INTO KPI_THRESHOLD (threshold_id, client_id, kpi_key, target_value,"
            " warning_threshold, critical_threshold, unit, higher_is_better)"
            " VALUES ('MINE', NULL, 'efficiency', 62.5, 55.0, 40.0, '%', 'Y')"
        )
        conn.commit()
        conn.close()

        command.upgrade(_config(at_previous), REVISION)

        target, warning, critical, _unit, _higher, threshold_id = _globals(at_previous)["efficiency"]
        assert (target, warning, critical) == (62.5, 55.0, 40.0), "the migration overwrote configuration"
        assert threshold_id == "MINE"

    def test_the_remaining_keys_are_still_supplied(self, at_previous):
        # Partial prior configuration must not short-circuit the whole insert.
        conn = sqlite3.connect(at_previous)
        conn.execute(
            "INSERT INTO KPI_THRESHOLD (threshold_id, client_id, kpi_key, target_value, unit, higher_is_better)"
            " VALUES ('MINE', NULL, 'efficiency', 62.5, '%', 'Y')"
        )
        conn.commit()
        conn.close()

        command.upgrade(_config(at_previous), REVISION)

        assert set(_globals(at_previous)) == set(EXPECTED)

    def test_a_client_specific_row_is_left_alone(self, at_previous):
        conn = sqlite3.connect(at_previous)
        conn.execute(
            "INSERT INTO CLIENT (client_id, client_name, client_type, is_active)" " VALUES ('C1', 'T', 'Other', 1)"
        )
        conn.execute(
            "INSERT INTO KPI_THRESHOLD (threshold_id, client_id, kpi_key, target_value, unit, higher_is_better)"
            " VALUES ('C1-EFF', 'C1', 'efficiency', 70.0, '%', 'Y')"
        )
        conn.commit()
        conn.close()

        command.upgrade(_config(at_previous), REVISION)

        conn = sqlite3.connect(at_previous)
        try:
            row = conn.execute(
                "SELECT target_value FROM KPI_THRESHOLD WHERE client_id = 'C1' AND kpi_key = 'efficiency'"
            ).fetchone()
        finally:
            conn.close()
        assert row == (70.0,)


class TestReversibility:
    def test_downgrade_removes_only_this_migrations_rows(self, at_previous):
        conn = sqlite3.connect(at_previous)
        conn.execute(
            "INSERT INTO KPI_THRESHOLD (threshold_id, client_id, kpi_key, target_value, unit, higher_is_better)"
            " VALUES ('MINE', NULL, 'quality', 99.0, '%', 'Y')"
        )
        conn.commit()
        conn.close()

        cfg = _config(at_previous)
        command.upgrade(cfg, REVISION)
        command.downgrade(cfg, PREVIOUS)

        # The administrator's own global row survives; the supplied defaults go.
        assert set(_globals(at_previous)) == {"quality"}

    def test_downgrade_keeps_a_pre_existing_row_that_shares_our_id(self, at_previous):
        """The case matching on threshold_id alone would have destroyed.

        `upgrade` skips a key that is already configured. If that pre-existing row
        happens to carry this migration's own id, an id-only delete would remove
        it on downgrade even though the migration never inserted it -- losing
        configuration a downgrade must not touch.
        """
        conn = sqlite3.connect(at_previous)
        conn.execute(
            "INSERT INTO KPI_THRESHOLD (threshold_id, client_id, kpi_key, target_value,"
            " warning_threshold, critical_threshold, unit, higher_is_better)"
            " VALUES ('THR-GLOBAL-EFFICIENCY', NULL, 'efficiency', 62.5, 55.0, 40.0, '%', 'Y')"
        )
        conn.commit()
        conn.close()

        cfg = _config(at_previous)
        command.upgrade(cfg, REVISION)
        command.downgrade(cfg, PREVIOUS)

        rows = _globals(at_previous)
        assert "efficiency" in rows, "downgrade deleted a row it never inserted"
        assert rows["efficiency"][0] == 62.5, rows["efficiency"]

    def test_downgrade_still_removes_a_row_it_did_insert(self, at_previous):
        # The other side: an untouched default must not survive a downgrade, or
        # the column-matching above would have made downgrade a no-op.
        cfg = _config(at_previous)
        command.upgrade(cfg, REVISION)
        command.downgrade(cfg, PREVIOUS)

        assert _globals(at_previous) == {}

    def test_upgrade_is_idempotent_across_a_downgrade_and_back(self, at_previous):
        cfg = _config(at_previous)
        command.upgrade(cfg, REVISION)
        first = _globals(at_previous)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, REVISION)

        assert _globals(at_previous) == first
