"""
Tests for Alembic schema migration setup.

Verifies that:
- alembic.ini exists and is parseable
- env.py can import all required models
- target_metadata has all expected tables registered
- Baseline migration has correct revision ID
- CLI commands (current, heads, upgrade head, stamp head) work correctly
"""

import configparser
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Root of the backend package (…/backend)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


# ---------------------------------------------------------------------------
# 1. alembic.ini exists and is parseable
# ---------------------------------------------------------------------------


class TestAlembicIni:
    """Tests for alembic.ini configuration file."""

    def test_alembic_ini_exists(self):
        assert ALEMBIC_INI.is_file(), f"alembic.ini not found at {ALEMBIC_INI}"

    def test_alembic_ini_parseable(self):
        cfg = configparser.ConfigParser()
        cfg.read(str(ALEMBIC_INI))
        assert "alembic" in cfg.sections(), "Missing [alembic] section"

    def test_script_location(self):
        cfg = configparser.ConfigParser()
        cfg.read(str(ALEMBIC_INI))
        assert cfg.get("alembic", "script_location") == "alembic"

    def test_file_template_has_timestamp(self):
        cfg = configparser.ConfigParser()
        cfg.read(str(ALEMBIC_INI))
        tpl = cfg.get("alembic", "file_template")
        # The template should contain year/month/day placeholders
        assert "year" in tpl
        assert "month" in tpl
        assert "rev" in tpl

    def test_prepend_sys_path(self):
        cfg = configparser.ConfigParser()
        cfg.read(str(ALEMBIC_INI))
        # Must be ".." so backend.* imports resolve from repo root
        assert cfg.get("alembic", "prepend_sys_path") == ".."


# ---------------------------------------------------------------------------
# 2. Model imports and metadata
# ---------------------------------------------------------------------------


class TestModelMetadata:
    """Verify that importing env.py registers all expected tables."""

    def test_base_metadata_has_core_tables(self):
        """Core tables created by backend.orm must be in Base.metadata."""
        from backend.database import Base

        import backend.orm  # noqa: F401
        import backend.orm.capacity  # noqa: F401

        table_names = set(Base.metadata.tables.keys())

        # Spot-check several core tables (use lowercase — SQLAlchemy stores LC)
        expected_core = {
            "CLIENT",
            "USER",
            "SHIFT",
            "EMPLOYEE",
            "PRODUCT",
            "WORK_ORDER",
            "PRODUCTION_ENTRY",
            "HOLD_ENTRY",
            "DOWNTIME_ENTRY",
            "ATTENDANCE_ENTRY",
            "QUALITY_ENTRY",
            "DEFECT_DETAIL",
        }
        for tbl in expected_core:
            assert tbl in table_names, f"Expected core table {tbl!r} not in metadata"

    def test_base_metadata_has_capacity_tables(self):
        """Capacity planning tables must be in Base.metadata."""
        from backend.database import Base

        import backend.orm.capacity  # noqa: F401

        table_names = set(Base.metadata.tables.keys())

        expected_capacity = {
            "capacity_calendar",
            "capacity_production_lines",
            "capacity_orders",
            "capacity_production_standards",
            "capacity_bom_header",
            "capacity_bom_detail",
            "capacity_stock_snapshot",
            "capacity_component_check",
            "capacity_analysis",
            "capacity_schedule",
            "capacity_schedule_detail",
            "capacity_scenario",
            "capacity_kpi_commitment",
        }
        for tbl in expected_capacity:
            assert tbl in table_names, f"Expected capacity table {tbl!r} not in metadata"

    def test_metadata_table_count_minimum(self):
        """Sanity check — we expect at least 25 tables total."""
        from backend.database import Base

        import backend.orm  # noqa: F401
        import backend.orm.capacity  # noqa: F401

        assert len(Base.metadata.tables) >= 25, f"Expected >= 25 tables, got {len(Base.metadata.tables)}"


# ---------------------------------------------------------------------------
# 3. Baseline migration validation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline_module():
    """Import the real baseline migration via importlib (digit-prefixed filename)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "baseline",
        str(BACKEND_DIR / "alembic" / "versions" / "0001_real_baseline.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBaselineMigrationImportlib:
    """Baseline migration revision-metadata tests (importlib avoids digit-prefix issues)."""

    def test_revision_id(self, baseline_module):
        assert baseline_module.revision == "0001_baseline"

    def test_down_revision_is_none(self, baseline_module):
        assert baseline_module.down_revision is None

    def test_branch_labels_is_none(self, baseline_module):
        assert baseline_module.branch_labels is None

    def test_depends_on_is_none(self, baseline_module):
        assert baseline_module.depends_on is None


class TestBaselineMigrationRuns:
    """The real baseline creates/drops the full schema; exercise both directions
    against a throwaway SQLite DB (upgrade()/downgrade() need a live Alembic
    migration context, so they cannot be called bare)."""

    def test_upgrade_head_creates_full_schema(self, tmp_path):
        from alembic import command
        from sqlalchemy import create_engine, inspect

        from backend.db.migrate import alembic_config

        url = f"sqlite:///{tmp_path}/baseline_up.db"
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        try:
            tables = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        assert {"USER", "CLIENT", "PRODUCTION_ENTRY"} <= tables

    def test_downgrade_base_drops_everything(self, tmp_path):
        from alembic import command
        from sqlalchemy import create_engine, inspect

        from backend.db.migrate import alembic_config

        url = f"sqlite:///{tmp_path}/baseline_down.db"
        cfg = alembic_config(url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        engine = create_engine(url)
        try:
            remaining = [t for t in inspect(engine).get_table_names() if t != "alembic_version"]
        finally:
            engine.dispose()
        assert remaining == []


# ---------------------------------------------------------------------------
# 4. Alembic CLI commands (subprocess — isolated from test DB state)
# ---------------------------------------------------------------------------


def _run_alembic(*args: str, db_url: str | None = None) -> subprocess.CompletedProcess:
    """Run ``python -m alembic <args>`` from the backend directory.

    ``db_url`` overrides DATABASE_URL for the subprocess so migration commands
    run against a throwaway database, never the developer's default DB file.
    """
    cmd = [sys.executable, "-m", "alembic"] + list(args)
    env = os.environ.copy()
    if db_url is not None:
        env["DATABASE_URL"] = db_url
    return subprocess.run(
        cmd,
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


class TestAlembicCLI:
    """Integration tests that exercise the Alembic CLI."""

    def test_alembic_heads(self):
        """``alembic heads`` should list the baseline revision."""
        result = _run_alembic("heads")
        assert result.returncode == 0, f"alembic heads failed: {result.stderr}"
        assert "0001_baseline" in result.stdout, f"0001_baseline not in heads output: {result.stdout}"

    def test_alembic_history(self):
        """``alembic history`` should contain the baseline entry."""
        result = _run_alembic("history")
        assert result.returncode == 0, f"alembic history failed: {result.stderr}"
        assert "0001_baseline" in result.stdout, f"0001_baseline not in history output: {result.stdout}"

    def test_alembic_current(self, tmp_path):
        """``alembic current`` should run without error against a fresh DB.

        The output is empty (no stamp yet) — that is expected.
        """
        url = f"sqlite:///{tmp_path}/cli_current.db"
        result = _run_alembic("current", db_url=url)
        assert result.returncode == 0, f"alembic current failed: {result.stderr}"

    def test_alembic_upgrade_head(self, tmp_path):
        """``alembic upgrade head`` should build the real baseline schema."""
        url = f"sqlite:///{tmp_path}/cli_upgrade.db"
        result = _run_alembic("upgrade", "head", db_url=url)
        assert result.returncode == 0, f"alembic upgrade head failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_alembic_stamp_head(self, tmp_path):
        """``alembic stamp head`` should succeed (marks DB at current revision)."""
        url = f"sqlite:///{tmp_path}/cli_stamp.db"
        result = _run_alembic("stamp", "head", db_url=url)
        assert result.returncode == 0, f"alembic stamp head failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_alembic_current_after_stamp(self, tmp_path):
        """After stamping, ``alembic current`` should report 0001_baseline."""
        url = f"sqlite:///{tmp_path}/cli_current_after_stamp.db"
        stamp = _run_alembic("stamp", "head", db_url=url)
        assert stamp.returncode == 0, f"alembic stamp head failed: {stamp.stderr}"
        result = _run_alembic("current", db_url=url)
        assert result.returncode == 0, f"alembic current failed: {result.stderr}"
        assert "0001_baseline" in result.stdout, f"Expected 0001_baseline in current output: {result.stdout}"
