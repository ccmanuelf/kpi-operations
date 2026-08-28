"""0007's downgrade drops ``is_active``, resurrecting every soft-deleted row.

It does so silently — ``deleted_at`` and ``deleted_by`` go with the column, so a
resurrected row is indistinguishable from one that was never deleted. The
migration refuses instead, unless the operator acknowledges it.

Mutation proof: delete the ``if counts and ...: raise`` block from
``downgrade()`` and ``test_downgrade_refuses_while_soft_deleted_rows_exist``
fails — the downgrade simply succeeds.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

MIGRATION_PATH = Path("alembic/versions/0007_transaction_soft_delete.py")


def _migration_module():
    """Load 0007 directly so the test pins the real constants, not copies."""
    spec = importlib.util.spec_from_file_location("_mig0007", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _migration_module()
ENV_VAR = MIGRATION.ACKNOWLEDGE_RESURRECTION_ENV


def _minimal_row(conn, engine, table):
    """INSERT one row using only the columns SQLite would reject as NULL.

    Built from PRAGMA rather than hand-written so this does not silently rot
    when a NOT NULL column is added to WORK_ORDER, and issued through
    SQLAlchemy Core so the statement is parameterised and the identifier is
    quoted by the dialect — the same construction the guard itself uses.
    """
    columns, values = [], {}
    for _, name, decl_type, notnull, default, _pk in conn.execute(f"PRAGMA table_info({table})"):
        if not notnull or default is not None:
            continue
        columns.append(name)
        upper = (decl_type or "").upper()
        if "INT" in upper:
            values[name] = 0
        elif any(t in upper for t in ("REAL", "FLOA", "DOUB", "NUMER", "DEC")):
            values[name] = 0.0
        elif "DATE" in upper or "TIME" in upper:
            values[name] = "2026-01-01 00:00:00"
        else:
            values[name] = "GUARD-TEST"
    target = sa.table(table, *[sa.column(c) for c in columns])
    with engine.begin() as connection:
        connection.execute(sa.insert(target).values(**values))


@pytest.fixture()
def at_0007(tmp_path):
    db_path = tmp_path / "sd_downgrade.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "0007_transaction_soft_delete")
    conn = sqlite3.connect(db_path)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        yield conn, cfg, engine
    finally:
        conn.close()
        engine.dispose()


def _soft_delete_one(conn, engine, table="WORK_ORDER"):
    _minimal_row(conn, engine, table)
    target = sa.table(table, sa.column("is_active"))
    with engine.begin() as connection:
        connection.execute(sa.update(target).values(is_active=0))


def test_downgrade_refuses_while_soft_deleted_rows_exist(at_0007, monkeypatch):
    conn, cfg, engine = at_0007
    monkeypatch.delenv(ENV_VAR, raising=False)
    _soft_delete_one(conn, engine)

    with pytest.raises(RuntimeError) as excinfo:
        command.downgrade(cfg, "0006_hold_status_history")

    message = str(excinfo.value)
    assert "WORK_ORDER (1)" in message
    assert ENV_VAR in message


def test_downgrade_leaves_the_columns_in_place_when_it_refuses(at_0007, monkeypatch):
    """A refusal must not be a half-applied downgrade."""
    conn, cfg, engine = at_0007
    monkeypatch.delenv(ENV_VAR, raising=False)
    _soft_delete_one(conn, engine)

    with pytest.raises(RuntimeError):
        command.downgrade(cfg, "0006_hold_status_history")

    columns = {row[1] for row in conn.execute("PRAGMA table_info(WORK_ORDER)")}
    assert {"is_active", "deleted_at", "deleted_by"} <= columns


def test_a_refusal_leaves_the_version_stamp_at_0007(at_0007, monkeypatch):
    """A refusal must not record a downgrade it did not perform.

    Checking the columns is not enough: if alembic_version moved to 0006 while
    the columns survived, the database would be lying about its own schema and
    the next upgrade would try to add columns that already exist.
    """
    conn, cfg, engine = at_0007
    monkeypatch.delenv(ENV_VAR, raising=False)
    _soft_delete_one(conn, engine)

    with pytest.raises(RuntimeError):
        command.downgrade(cfg, "0006_hold_status_history")

    with engine.begin() as connection:
        stamped = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert stamped == "0007_transaction_soft_delete"


def test_downgrade_proceeds_when_the_resurrection_is_acknowledged(at_0007, monkeypatch):
    conn, cfg, engine = at_0007
    _soft_delete_one(conn, engine)
    monkeypatch.setenv(ENV_VAR, "1")

    command.downgrade(cfg, "0006_hold_status_history")

    columns = {row[1] for row in conn.execute("PRAGMA table_info(WORK_ORDER)")}
    assert not ({"is_active", "deleted_at", "deleted_by"} & columns)


def test_downgrade_is_unobstructed_when_nothing_was_deleted(at_0007, monkeypatch):
    """The guard gates on data, not on the migration being present."""
    conn, cfg, engine = at_0007
    monkeypatch.delenv(ENV_VAR, raising=False)
    _minimal_row(conn, engine, "WORK_ORDER")  # active row: not a resurrection risk

    command.downgrade(cfg, "0006_hold_status_history")

    columns = {row[1] for row in conn.execute("PRAGMA table_info(WORK_ORDER)")}
    assert not ({"is_active", "deleted_at", "deleted_by"} & columns)


def test_guard_covers_every_table_the_migration_touches(at_0007):
    """The count query must span all of TABLES, not a subset someone typed."""
    conn, _, engine = at_0007
    for table in MIGRATION.TABLES:
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        assert "is_active" in columns, f"{table} has no is_active for the guard to count"


def test_a_half_applied_0007_says_how_to_recover(at_0007, monkeypatch):
    """The in-place edit of this revision is a documented footgun.

    A database stamped 0007 by an earlier version of it carries the columns on
    only some tables. That must fail with the remedy, not with a driver error
    about an unknown column.
    """
    conn, cfg, engine = at_0007
    monkeypatch.delenv(ENV_VAR, raising=False)
    with engine.begin() as connection:
        for name in ("is_active", "deleted_at", "deleted_by"):
            connection.execute(sa.text(f'ALTER TABLE "ALERT" DROP COLUMN "{name}"'))

    with pytest.raises(RuntimeError) as excinfo:
        command.downgrade(cfg, "0006_hold_status_history")

    message = str(excinfo.value)
    assert "ALERT" in message
    assert "alembic stamp 0006_hold_status_history" in message
