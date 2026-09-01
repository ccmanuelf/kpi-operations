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
from backend.seed.profiles import FULL
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
    """Two-sided. An assumption outside the catalog has no metric depending on
    it; a catalog entry left unseeded shows the screen a blank row."""
    with full_db.begin() as conn:
        seeded = {n for (n,) in conn.execute(text("SELECT DISTINCT assumption_name FROM CALCULATION_ASSUMPTION"))}
    assert seeded == set(V1_CATALOG), (
        f"not in catalog: {sorted(seeded - set(V1_CATALOG))}; "
        f"catalog entries unseeded: {sorted(set(V1_CATALOG) - seeded)}"
    )


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
        changed = {
            n
            for (n,) in conn.execute(
                text(
                    "SELECT DISTINCT a.assumption_name"
                    "  FROM ASSUMPTION_CHANGE c"
                    "  JOIN CALCULATION_ASSUMPTION a ON a.assumption_id = c.assumption_id"
                )
            )
        }
    expected = {n for n, _v, _d, dev, _r in CALCULATION_ASSUMPTIONS if dev}
    assert changed == expected, f"changed={sorted(changed)} expected={sorted(expected)}"


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
