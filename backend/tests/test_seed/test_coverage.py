from datetime import date

from sqlalchemy import func, select

from backend.database import Base
from backend.seed.coverage import NOT_SEEDED, SEEDED
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import SCENARIOS


def test_the_two_buckets_are_disjoint():
    assert SEEDED & set(NOT_SEEDED) == frozenset()


def test_every_declared_table_exists_in_the_schema():
    known = set(Base.metadata.tables)
    for name in SEEDED | set(NOT_SEEDED):
        assert name in known, f"{name} is declared but is not a table"


def test_not_seeded_holds_exactly_the_three_with_another_owner():
    """Spec section 7, widened twice as the seeder's reach grew.

    Each entry is excluded because something ELSE owns the rows, not because
    nobody got round to them:
      * TOKEN_BLACKLIST -- fabricated revoked tokens would demonstrate nothing
        and could only mislead;
      * METRIC_ASSUMPTION_DEPENDENCY -- the BOOT path seeds it from the
        authoritative assumption catalog (18 rows, verified on the VM), and a
        table with two owners is a table whose owners can disagree;
      * METRIC_CALCULATION_RESULT -- calculation output the dual-view
        scheduler recomputes nightly, so seeded values would be numbers no
        calculation produced.

    Pinned exactly so a table added here is a deliberate act with a stated
    owner, rather than a quiet way to stop covering something.
    """
    assert set(NOT_SEEDED) == {
        "TOKEN_BLACKLIST",
        "METRIC_ASSUMPTION_DEPENDENCY",
        "METRIC_CALCULATION_RESULT",
    }


def test_every_exclusion_carries_a_reason():
    for name, reason in NOT_SEEDED.items():
        assert len(reason) > 30, f"{name}'s exclusion reason is not an explanation"


def test_every_seeded_table_actually_has_rows(seed_engine):
    """The gate. A table declared seeded but left empty is the failure this
    contract exists to make loud."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=date(2026, 8, 18))
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    empty = []
    with seed_engine.connect() as conn:
        for name in sorted(SEEDED):
            table = Base.metadata.tables[name]
            if conn.execute(select(func.count()).select_from(table)).scalar_one() == 0:
                empty.append(name)

    assert empty == []


def test_the_materializer_writes_nothing_outside_the_contract(seed_engine):
    """The other direction: a table written but not declared is a table the
    contract does not govern."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=date(2026, 8, 18))
    with seed_engine.begin() as conn:
        counts = materialize(conn, events, SMOKE)

    assert set(counts) - SEEDED == set()
