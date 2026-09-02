"""The machine registry and DPMO metadata, asserted against a FULL seeded database.

Both tables were empty in every demo before this, and each empty table hid a
feature rather than merely showing a short list. These pin the two things that
made them worth seeding at all:

  * a shared machine exists and carries no line, because GET
    /api/equipment/shared filters on is_shared and could otherwise only ever
    return [];
  * every part a JOB names has an opportunities row, because
    get_opportunities_for_part falls back to a client default when nothing
    matches -- so a mismatched part number reads the fallback while looking
    configured.
"""

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.calculations.dpmo import get_opportunities_for_part
from backend.orm.equipment import Equipment
from backend.schemas.equipment import EquipmentResponse
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 21)


@pytest.fixture(scope="module")
def full_db(seed_engine_module):
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine_module.begin() as conn:
        materialize(conn, events, FULL)
    return seed_engine_module


def test_every_equipment_row_survives_the_schema_its_endpoint_returns(full_db):
    broken = []
    with Session(bind=full_db) as session:
        rows = session.query(Equipment).all()
        assert rows, "no EQUIPMENT rows seeded"
        for row in rows:
            try:
                EquipmentResponse.model_validate(row, from_attributes=True)
            except Exception as exc:
                broken.append(f"{row.equipment_code}: {exc}")
    assert not broken, "seeded equipment the endpoint cannot serialize:\n  " + "\n  ".join(broken)


def test_every_client_owns_a_shared_machine_and_it_hangs_off_no_line(full_db):
    """GET /api/equipment/shared filters is_shared=True; list_equipment treats
    a shared machine as visible from every line, which only works when
    line_id is NULL."""
    with full_db.begin() as conn:
        per_client = dict(
            conn.execute(text("SELECT client_id, COUNT(*) FROM EQUIPMENT WHERE is_shared = 1 GROUP BY client_id")).all()
        )
        # From CLIENT, not from EQUIPMENT. Taking the universe from the table
        # under test made a client with NO equipment at all invisible here --
        # the one case where /equipment/shared certainly returns [].
        clients = {c for (c,) in conn.execute(text("SELECT client_id FROM CLIENT"))}
        attached = conn.execute(
            text("SELECT COUNT(*) FROM EQUIPMENT WHERE is_shared = 1 AND line_id IS NOT NULL")
        ).scalar_one()
    missing = sorted(clients - set(per_client))
    assert not missing, f"clients whose /equipment/shared can only return []: {missing}"
    assert attached == 0, f"{attached} shared machines are pinned to one line"


def test_no_machine_points_at_another_clients_line(full_db):
    """line_id is resolved through the IdMap from a seed key; a key collision
    across clients would silently attach a machine to another tenant's line."""
    with full_db.begin() as conn:
        wrong = conn.execute(
            text(
                "SELECT COUNT(*) FROM EQUIPMENT e"
                "  JOIN PRODUCTION_LINE l ON l.line_id = e.line_id"
                " WHERE l.client_id <> e.client_id"
            )
        ).scalar_one()
    assert wrong == 0, f"{wrong} machines attached to another client's line"


def test_the_registry_spans_the_axes_its_filters_use(full_db):
    """status is the lifecycle the CheckConstraint enforces; is_active is the
    soft-delete flag list_equipment's include_inactive toggles. A registry
    holding one value of either never shows what the filter does."""
    with full_db.begin() as conn:
        statuses = {s for (s,) in conn.execute(text("SELECT DISTINCT status FROM EQUIPMENT"))}
        actives = {bool(a) for (a,) in conn.execute(text("SELECT DISTINCT is_active FROM EQUIPMENT"))}
    assert statuses == {"ACTIVE", "MAINTENANCE", "RETIRED"}, f"statuses seeded: {sorted(statuses)}"
    assert actives == {True, False}, "nothing is soft-deleted, so include_inactive shows the same list"


def test_every_part_a_job_names_has_its_own_opportunity_count(full_db):
    """Two-sided. A job part with no row reads the client default while
    appearing configured; an opportunities row no job references is dead
    metadata pointing at a part that does not exist."""
    with full_db.begin() as conn:
        unmatched = conn.execute(
            text(
                "SELECT COUNT(DISTINCT j.part_number) FROM JOB j"
                "  LEFT JOIN PART_OPPORTUNITIES p ON p.part_number = j.part_number"
                " WHERE p.part_number IS NULL"
            )
        ).scalar_one()
        orphaned = conn.execute(
            text(
                "SELECT COUNT(*) FROM PART_OPPORTUNITIES p"
                "  LEFT JOIN JOB j ON j.part_number = p.part_number"
                " WHERE j.part_number IS NULL"
            )
        ).scalar_one()
        cross_tenant = conn.execute(
            text(
                "SELECT COUNT(*) FROM PART_OPPORTUNITIES p"
                "  JOIN JOB j ON j.part_number = p.part_number"
                " WHERE j.client_id_fk <> p.client_id_fk"
            )
        ).scalar_one()
    assert unmatched == 0, f"{unmatched} job parts fall back to the client default"
    assert orphaned == 0, f"{orphaned} opportunity rows name a part no job runs"
    assert cross_tenant == 0, f"{cross_tenant} opportunity rows belong to another tenant"


def test_the_seeded_count_is_distinguishable_from_the_fallback(full_db):
    """If the seeded value equalled the default, the table could be empty and
    every DPMO would be identical -- the seeding would demonstrate nothing."""
    with Session(bind=full_db) as session:
        part = session.execute(text("SELECT part_number FROM PART_OPPORTUNITIES LIMIT 1")).scalar_one()
        seeded = get_opportunities_for_part(session, part)
        fallback = get_opportunities_for_part(session, "NO-SUCH-PART-EXISTS")
    assert seeded > 0
    assert seeded != fallback, (
        f"seeded opportunities ({seeded}) equal the fallback default ({fallback}); "
        "an empty table would produce the same DPMO"
    )
