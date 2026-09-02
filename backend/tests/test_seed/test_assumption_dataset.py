"""The assumptions and saved simulations, asserted against a FULL seeded database.

Each of these pins something that was WRONG while this data was written:

  * every saved scenario carried horizon_days=30 against an engine that caps
    the horizon at 7 -- all 8 rows loaded into a form the engine refuses to
    run, which is worse than seeding no scenario at all;
  * the assumption rows were first written without proposed_by/proposed_at,
    columns the table declares NOT NULL.

The catalog gate is two-sided on purpose: seeding an assumption the engine
does not know, or leaving one of its six unseeded, both fail here.
"""

import json
from datetime import date

import pytest
from sqlalchemy import text

from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import FULL, SMOKE
from backend.seed.scenarios import CALCULATION_ASSUMPTIONS, SCENARIOS
from backend.services.calculations.assumption_catalog import V1_CATALOG
from backend.simulation_v2.models import SimulationConfig
from backend.simulation_v2.validation import validate_simulation_config

AS_OF = date(2026, 8, 21)


@pytest.fixture(scope="module")
def full_db(seed_engine_module):
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine_module.begin() as conn:
        materialize(conn, events, FULL)
    return seed_engine_module


def _configs(conn):
    return [
        (name, json.loads(cfg) if isinstance(cfg, str) else cfg)
        for name, cfg in conn.execute(text("SELECT name, config_json FROM SIMULATION_SCENARIO"))
    ]


def test_every_saved_scenario_loads_into_the_engines_own_schema(full_db):
    """A scenario the engine cannot parse is a dead row on the screen. This
    caught horizon_days=30 against MAX_HORIZON_DAYS=7, on all 8 rows."""
    with full_db.begin() as conn:
        rows = _configs(conn)
    assert rows, "no simulation scenarios seeded"
    broken = []
    for name, cfg in rows:
        try:
            SimulationConfig.model_validate(cfg)
        except Exception as exc:  # pragma: no cover - only on regression
            fields = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
            broken.append(f"{name}: {fields}")
    assert not broken, "saved scenarios the engine cannot load:\n  " + "\n  ".join(broken)


def test_every_saved_scenario_survives_the_domain_validator(full_db):
    """Schema-valid is not the same as runnable: the domain validator is what
    the run button consults before it starts the simulation."""
    with full_db.begin() as conn:
        rows = _configs(conn)
    blocked = []
    for name, cfg in rows:
        report = validate_simulation_config(SimulationConfig.model_validate(cfg))
        if not report.can_proceed:
            blocked.append(f"{name}: {[i.message for i in report.errors]}")
    assert not blocked, "saved scenarios the engine would refuse to run:\n  " + "\n  ".join(blocked)


def test_seeded_assumptions_are_exactly_the_catalog(full_db):
    """Two-sided, and PER CLIENT. An assumption outside the catalog has no
    metric depending on it; a catalog entry left unseeded shows the screen a
    blank row.

    Aggregating across clients made this vacuous in the direction that matters:
    assumptions are client-scoped and the dual view resolves them per tenant,
    so seeding all six for ONE client and none for the other three satisfied a
    flat DISTINCT over the whole table.
    """
    with full_db.begin() as conn:
        tenants = {c for (c,) in conn.execute(text("SELECT client_id FROM CLIENT"))}
        rows = list(conn.execute(text("SELECT client_id, assumption_name FROM CALCULATION_ASSUMPTION")))
    assert tenants, "no clients seeded"
    per_client: dict = {}
    for client_id, name in rows:
        per_client.setdefault(client_id, set()).add(name)
    wrong = []
    for client_id in sorted(tenants):
        seeded = per_client.get(client_id, set())
        if seeded != set(V1_CATALOG):
            wrong.append(
                f"{client_id}: not in catalog={sorted(seeded - set(V1_CATALOG))} "
                f"unseeded={sorted(set(V1_CATALOG) - seeded)}"
            )
    assert not wrong, "clients whose assumption set is not the catalog:\n  " + "\n  ".join(wrong)


def test_every_assumption_value_is_one_the_catalog_allows(full_db):
    """Not every entry is an enum: otd_carrier_buffer_pct is a free percentage
    and carries allowed_values=None, so membership only applies where a set
    was declared."""
    with full_db.begin() as conn:
        rows = list(conn.execute(text("SELECT assumption_name, value_json FROM CALCULATION_ASSUMPTION")))
    illegal = []
    for n, v in rows:
        allowed = V1_CATALOG[n]["allowed_values"]
        value = json.loads(v)
        if allowed is None:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                illegal.append(f"{n}={v} (free-valued, expected a number)")
        elif value not in allowed:
            illegal.append(f"{n}={v}")
    assert not illegal, f"values outside the catalog's allowed set: {illegal}"


def test_the_seeds_restated_defaults_match_the_catalog():
    """scenarios.py restates default_value because assumption_catalog imports
    Session. A drifted restatement seeds a history row claiming the site moved
    away from a default that was never the default."""
    wrong = [
        f"{name}: seed={default!r} catalog={V1_CATALOG[name]['default_value']!r}"
        for name, _v, default, _d, _r in CALCULATION_ASSUMPTIONS
        if default != V1_CATALOG[name]["default_value"]
    ]
    assert not wrong, f"restated defaults drifted from the catalog: {wrong}"


def test_the_deviates_flag_agrees_with_the_catalog_default():
    """The flag drives which assumptions get a change row. If it disagrees with
    the catalog, the audit trail describes changes that never happened."""
    wrong = [
        name
        for name, value, _default, deviates, _r in CALCULATION_ASSUMPTIONS
        if (value != V1_CATALOG[name]["default_value"]) is not deviates
    ]
    assert not wrong, f"deviates_from_default disagrees with the catalog for: {wrong}"


def test_change_history_covers_exactly_the_assumptions_that_deviate(full_db):
    """An unchanged assumption with a change row is a fabricated audit trail."""
    with full_db.begin() as conn:
        rows = list(
            conn.execute(
                text(
                    "SELECT a.client_id, a.assumption_name, COUNT(*)"
                    "  FROM ASSUMPTION_CHANGE c"
                    "  JOIN CALCULATION_ASSUMPTION a ON a.assumption_id = c.assumption_id"
                    " GROUP BY a.client_id, a.assumption_name"
                )
            )
        )
        tenants = {c for (c,) in conn.execute(text("SELECT client_id FROM CLIENT"))}
    expected = {n for n, _v, _d, dev, _r in CALCULATION_ASSUMPTIONS if dev}
    # Per client AND with cardinality. A DISTINCT set comparison could see
    # neither a second, fabricated change row against the same assumption nor
    # a whole client whose history was never written.
    by_client: dict = {}
    for client_id, name, count in rows:
        by_client.setdefault(client_id, {})[name] = count
    wrong = []
    for client_id in sorted(tenants):
        got = by_client.get(client_id, {})
        if set(got) != expected:
            wrong.append(f"{client_id}: changed={sorted(got)} expected={sorted(expected)}")
        duplicated = {n: c for n, c in got.items() if c != 1}
        if duplicated:
            wrong.append(f"{client_id}: more than one change row for {duplicated}")
    assert not wrong, "assumption history does not match the deviations:\n  " + "\n  ".join(wrong)


def test_a_changes_previous_value_is_the_catalog_default(full_db):
    """The row says what it moved away from; if that is not the default, the
    trail contradicts the catalog it was derived from."""
    with full_db.begin() as conn:
        rows = list(
            conn.execute(
                text(
                    "SELECT a.assumption_name, c.previous_value_json, c.new_value_json"
                    "  FROM ASSUMPTION_CHANGE c"
                    "  JOIN CALCULATION_ASSUMPTION a ON a.assumption_id = c.assumption_id"
                )
            )
        )
    assert rows, "no change rows seeded"
    bad = [
        f"{n}: from={prev} to={new}"
        for n, prev, new in rows
        if json.loads(prev) != V1_CATALOG[n]["default_value"] or json.loads(new) == json.loads(prev)
    ]
    assert not bad, f"change rows that misstate the move: {bad}"


def test_only_the_run_scenario_carries_results(full_db):
    """Saved and executed are different states; if every scenario has results,
    the run button has nothing left to express."""
    with full_db.begin() as conn:
        rows = list(conn.execute(text("SELECT name, last_run_summary, last_run_at FROM SIMULATION_SCENARIO")))

    def absent(raw):
        """The column is JSON, so an unrun scenario holds the JSON literal
        `null`, not SQL NULL -- SQLAlchemy reads both back as None, but raw
        SQL does not. Both spellings mean 'never run'."""
        if raw is None:
            return True
        return (json.loads(raw) if isinstance(raw, (str, bytes)) else raw) is None

    with_results = {n for n, summary, _ in rows if not absent(summary)}
    assert with_results, "no scenario carries a run result"
    assert len(with_results) < len({n for n, _, _ in rows}), "every scenario carries results"
    mismatched = [n for n, summary, at in rows if absent(summary) != (at is None)]
    assert not mismatched, f"last_run_summary and last_run_at disagree for: {mismatched}"


def test_production_entries_carry_the_time_split_the_dual_view_reads(full_db):
    """aggregate_oee_inputs sums downtime, setup and maintenance off
    PRODUCTION_ENTRY and reads nothing else for non-run time -- it never
    touches DOWNTIME_ENTRY. All three columns were unwritten, so the dual view
    saw a factory that never stopped (OEE 99.5% on every client) and three of
    the six assumption rules operated on zeros.

    setup and maintenance are COMPONENTS of downtime, not additions to it:
    oee_service subtracts either one from downtime and scheduled hours
    together, so a setup larger than the downtime it sits inside would drive
    downtime negative and be clamped to zero.
    """
    with full_db.begin() as conn:
        totals = conn.execute(
            text(
                "SELECT SUM(downtime_hours), SUM(setup_time_hours), SUM(maintenance_hours), COUNT(*)"
                "  FROM PRODUCTION_ENTRY"
            )
        ).first()
        overrun = conn.execute(
            text(
                "SELECT COUNT(*) FROM PRODUCTION_ENTRY"
                " WHERE COALESCE(setup_time_hours, 0) + COALESCE(maintenance_hours, 0)"
                "     > COALESCE(downtime_hours, 0)"
            )
        ).scalar_one()
        reworked = conn.execute(text("SELECT SUM(units_reworked) FROM QUALITY_ENTRY")).scalar_one()

    downtime, setup, maintenance, rows = totals
    assert rows > 0, "no production entries seeded"
    assert downtime and downtime > 0, "the dual view sees a factory that never stopped"
    assert setup and setup > 0, "setup_treatment can only move a number when setup time exists"
    assert maintenance and maintenance > 0, "planned_production_time_basis needs maintenance hours"
    assert overrun == 0, f"{overrun} entries where setup + maintenance exceed the downtime they sit in"
    assert reworked and reworked > 0, "scrap_classification_rule is defined in terms of units_reworked"


def test_the_deviating_assumptions_actually_move_the_dual_view(full_db):
    """The point of deviating from the catalog default is that the two views
    differ. Both deviations were previously inert -- one read a column the
    seeder never wrote, the other a field aggregate_oee_inputs never populates
    -- so standard and site-adjusted agreed to the cent on every client and
    the delta column, which is the whole feature, was 0.00 everywhere.

    Asserted through the real service rather than by re-deriving the
    arithmetic: a test that recomputed the delta itself would agree with a
    seeder that had stopped moving it.
    """
    from datetime import date as _date

    from backend.orm.user import User
    from backend.services.dual_view.aggregators import aggregate_oee_inputs
    from backend.services.dual_view.oee_service import OEECalculationService
    from sqlalchemy.orm import Session

    start, end = _date(2026, 5, 1), AS_OF
    flat = []
    with Session(bind=full_db) as session:
        admin = session.query(User).filter(User.role == "admin").first()
        assert admin is not None, "no admin seeded to attribute the calculation to"
        service = OEECalculationService(session, admin)
        clients = [c for (c,) in session.execute(text("SELECT DISTINCT client_id FROM PRODUCTION_ENTRY"))]
        assert clients, "no clients with production to calculate"
        for client_id in clients:
            raw = aggregate_oee_inputs(session, client_id, start, end)
            result = service.calculate(client_id, start, end, raw, persist=False)
            if not result.delta:
                flat.append(f"{client_id}: standard == site_adjusted == {result.standard_value}")
    assert not flat, "clients whose dual view shows no delta at all:\n  " + "\n  ".join(flat)


def test_the_variance_report_shows_both_staleness_states(full_db):
    """`days_since_review` counts from approved_at and the report calls a row
    stale past its threshold. Approving all six on one day put every row at the
    same age -- and exactly ON the 365-day boundary, so the column showed one
    state and every row would flip together the day after the seed was taken.

    Asserted through the real service: the report is what the screen renders,
    and re-deriving the arithmetic here would agree with a seeder that had
    stopped straddling the boundary.
    """
    from backend.orm.user import User
    from backend.services.assumption_service import AssumptionService
    from sqlalchemy.orm import Session

    with Session(bind=full_db) as session:
        admin = session.query(User).filter(User.role == "admin").first()
        assert admin is not None
        rows = AssumptionService(session, admin).get_variance_report()

    def field(row, key):
        return row.get(key) if isinstance(row, dict) else getattr(row, key, None)

    assert rows, "the variance report is empty"
    unapproved = [r for r in rows if not field(r, "approved_by")]
    assert not unapproved, f"{len(unapproved)} rows are active with no approver"
    stale = [r for r in rows if field(r, "is_stale")]
    fresh = [r for r in rows if not field(r, "is_stale")]
    assert stale, "nothing is stale, so the staleness column and its badge show one state"
    assert fresh, "everything is stale, which demonstrates the column no better"


@pytest.mark.parametrize("profile", [FULL, SMOKE], ids=["full", "smoke"])
def test_no_assumption_is_approved_before_it_was_proposed(profile):
    """Checked at the EVENT level and against BOTH profiles, because the bug
    this catches was a property of the profile rather than of the data.

    The review dates were anchored to the activity window while `as_of` set the
    recent one. FULL opens its window 365 days before as_of, so the ordering
    held; SMOKE opens it 14 days before, so the "recent review" landed 30 days
    BEFORE the proposal it approved. A fixture that only ever built FULL could
    not see it.
    """
    from backend.seed.events import AssumptionRegistered

    events = [e for e in generate(SCENARIOS, profile, seed=1234, as_of=AS_OF) if isinstance(e, AssumptionRegistered)]
    assert events, f"no assumptions emitted for the {profile.name} profile"
    backwards = [
        f"{e.client_id}/{e.assumption_name}: proposed {e.proposed_at} approved {e.approved_at}"
        for e in events
        if e.approved_at is not None and e.approved_at < e.proposed_at
    ]
    assert not backwards, "approved before proposed:\n  " + "\n  ".join(backwards)


@pytest.mark.parametrize("profile", [FULL, SMOKE], ids=["full", "smoke"])
def test_both_staleness_states_survive_either_profile(profile):
    """The split has to come from the review dates themselves, not from how
    wide the profile's activity window happens to be."""
    from backend.seed.events import AssumptionRegistered

    ages = {
        (AS_OF - e.approved_at.date()).days
        for e in generate(SCENARIOS, profile, seed=1234, as_of=AS_OF)
        if isinstance(e, AssumptionRegistered) and e.approved_at is not None
    }
    assert any(age > 365 for age in ages), f"nothing is stale in {profile.name}: ages {sorted(ages)}"
    assert any(age <= 365 for age in ages), f"nothing is fresh in {profile.name}: ages {sorted(ages)}"
