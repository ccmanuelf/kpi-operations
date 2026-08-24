"""What a re-seed must PRESERVE: idempotency, and tenant-adjacent data the
seeder never wrote surviving --reset untouched.

Split out of test_cli.py's original body. test_cli.py keeps the CLI surface
and contract tests; test_cli_reset_sweep.py covers how the --reset sweep
traverses foreign keys to reach the right rows; test_cli_derived_sets.py
covers the structural guards over derived table sets.
"""

from datetime import date

from sqlalchemy import func, insert, select

from backend.database import Base
from backend.seed.cli import ALLOWLIST, seed
from backend.tests.test_seed._reset_row_builders import _insert_alert_config


def test_reset_deletes_only_allowlisted_client_rows(seed_engine):
    """--reset must leave every other tenant untouched.

    REAL-CUSTOMER is given a CHILD row here, in a client-scoped table the
    seeder never writes. Without it this test proved almost nothing about the
    scoped sweep: a bare CLIENT row is deleted last and blocks nothing, which
    is precisely why C-2 -- a --reset that crashed the moment any demo tenant
    owned a row outside `SEEDED` -- reached review with a green suite.

    It is also given a PRODUCTION_LINE hierarchy, because --reset does not
    only DELETE any more: SELF_REFERENTIAL_SWEEPS issues an UPDATE that NULLs
    parent_line_id. An UPDATE with no tenant filter is silent -- it raises
    nothing, changes no row count, and leaves every assertion above green
    while quietly flattening a real customer's line hierarchy across the whole
    database. Dropping `.where(...)` from that one statement is an ordinary
    refactor slip with cross-tenant consequences on the production VM, so it
    gets an assertion rather than a comment.
    """
    client = Base.metadata.tables["CLIENT"]
    alert_config = Base.metadata.tables["ALERT_CONFIG"]
    production_line = Base.metadata.tables["PRODUCTION_LINE"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client),
            [{"client_id": "REAL-CUSTOMER", "client_name": "Real", "client_type": "Hourly Rate", "is_active": True}],
        )
        _insert_alert_config(conn, "REAL-CUSTOMER")
        parent_id = conn.execute(
            insert(production_line).values(client_id="REAL-CUSTOMER", line_code="REAL-L1", line_name="Real Parent Line")
        ).inserted_primary_key[0]
        conn.execute(
            insert(production_line).values(
                client_id="REAL-CUSTOMER",
                line_code="REAL-L1-A",
                line_name="Real Child Line",
                parent_line_id=parent_id,
            )
        )

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=True, **kwargs)
    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        survivors = conn.execute(select(client.c.client_id).where(client.c.client_id == "REAL-CUSTOMER")).all()
        real_configs = conn.execute(
            select(func.count()).select_from(alert_config).where(alert_config.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
        demo = conn.execute(
            select(func.count()).select_from(client).where(client.c.client_id == "DEMO-PIECE")
        ).scalar_one()
        real_parents = (
            conn.execute(
                select(production_line.c.parent_line_id).where(
                    production_line.c.client_id == "REAL-CUSTOMER",
                    production_line.c.line_code == "REAL-L1-A",
                )
            )
            .scalars()
            .all()
        )

    assert len(survivors) == 1
    assert real_configs == 1, "the widened sweep reached a tenant that was never asked for"
    assert demo == 1, "a second --reset seed must not duplicate the client row"
    assert real_parents == [parent_id], "the self-referential UPDATE flattened a tenant that was never asked for"


# --- Additional coverage: traps the brief's own tests do not exercise ------


def test_reset_preserves_a_users_saved_filter_across_reseed(seed_engine):
    """The reviewer's repro. A live survey of every FK into USER.user_id found
    ~10 tables outside S1b's declared scope (SAVED_FILTER,
    ALERT.acknowledged_by/resolved_by, IMPORT_LOG, COVERAGE_ENTRY,
    CALCULATION_ASSUMPTION, METRIC_CALCULATION_RESULT, SIMULATION_SCENARIO,
    EVENT_STORE) with no ondelete cascade -- an unconditional USER delete on
    --reset RESTRICTs the moment a demo user has used one of those features.
    This seeds, inserts a SAVED_FILTER row for USR-DEMO-OP exactly as the live
    app does when a user saves a dashboard filter, then --reset + reseeds:
    must not raise, and the filter must survive (USER is never deleted, so
    its child row never becomes an orphan)."""
    saved_filter = Base.metadata.tables["SAVED_FILTER"]
    kwargs = dict(client_ids=tuple(ALLOWLIST), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))

    seed(seed_engine, reset=False, **kwargs)

    with seed_engine.begin() as conn:
        conn.execute(
            insert(saved_filter),
            [
                {
                    "user_id": "USR-DEMO-OP",
                    "filter_name": "My Dashboard",
                    "filter_type": "dashboard",
                    "filter_config": '{"client_id": "DEMO-PIECE"}',
                }
            ],
        )

    # Must not raise -- this is the reviewer's repro (previously a
    # sqlite3.IntegrityError: FOREIGN KEY constraint failed deleting USER).
    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        survivors = conn.execute(
            select(func.count()).select_from(saved_filter).where(saved_filter.c.user_id == "USR-DEMO-OP")
        ).scalar_one()

    assert survivors == 1


def test_reset_reseed_cycle_keeps_exactly_six_users_and_never_collides(seed_engine):
    """User creation is idempotent (seed() drops UserCreated events for ids
    that already exist), not delete-then-recreate. Run seed / --reset+seed /
    --reset+seed and assert exactly six users survive at every step, with no
    PK-collision IntegrityError anywhere in the cycle."""
    user = Base.metadata.tables["USER"]
    kwargs = dict(client_ids=tuple(ALLOWLIST), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))

    def count_users() -> int:
        with seed_engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(user)).scalar_one())

    seed(seed_engine, reset=False, **kwargs)
    assert count_users() == 6

    seed(seed_engine, reset=True, **kwargs)
    assert count_users() == 6

    seed(seed_engine, reset=True, **kwargs)
    assert count_users() == 6


def test_reset_does_not_duplicate_kpi_thresholds_on_reseed(seed_engine):
    """KPI_THRESHOLD is client-scoped (real client_id under
    UniqueConstraint(client_id, kpi_key)) and is swept generically by _reset
    like any other client-scoped table -- no special-casing needed. A --reset
    bug here is silent (re-seed duplication), so assert the count directly:
    seed, reset+reseed twice, and confirm exactly one threshold set survives
    per client rather than eyeballing that the run didn't raise."""
    from backend.seed.scenarios import THRESHOLDS

    threshold = Base.metadata.tables["KPI_THRESHOLD"]
    kwargs = dict(
        client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18), reset=True
    )

    seed(seed_engine, **kwargs)
    seed(seed_engine, **kwargs)

    with seed_engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(threshold).where(threshold.c.client_id == "DEMO-PIECE")
        ).scalar_one()

    assert count == len(THRESHOLDS)
