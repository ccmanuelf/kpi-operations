"""What the WIDENED stream contains: per-employee attendance, catalog-valid
defect codes and hold vocabularies, the work-order columns the tables require,
the six-role credential set, and attribution.

Split out of test_generator.py, which keeps the ordering and structural
properties of the stream as a whole -- sortedness, seq contiguity, referential
integrity in time, the as_of clamp. The seam is "is this about the SHAPE of the
stream or about what a given event SAYS".
"""

from collections import Counter
from datetime import date

from backend.seed.events import (
    AttendanceRecorded,
    ClientAccessGranted,
    DefectsFound,
    DefectTypeDefined,
    DowntimeLogged,
    HoldOpened,
    HoldReasonDefined,
    HoldStatusChanged,
    HoldStatusDefined,
    ProductionRecorded,
    QualityInspected,
    UserCreated,
    WorkOrderReceived,
)
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import FULL, SMOKE
from backend.seed.scenarios import DEFECT_CODES, HOLD_REASONS, HOLD_STATUSES, ROOT_CAUSES, SCENARIOS, USERS

AS_OF = date(2026, 8, 14)


def _gen(seed=1234):
    return generate(SCENARIOS, SMOKE, seed=seed, as_of=AS_OF)


def test_attendance_is_emitted_once_per_employee_per_worked_shift():
    """The headcount-only event could not express this; N rows per shift is the
    reason the model split."""
    events = _gen()
    attendance = [e for e in events if isinstance(e, AttendanceRecorded)]
    production = [e for e in events if isinstance(e, ProductionRecorded)]

    assert attendance
    per_shift = Counter((e.client_id, e.line_id, e.shift_id, e.shift_date) for e in attendance)
    # One production row per worked (client, line, shift, date); attendance is
    # one row per employee on that same key, so every key must exceed 1.
    assert len(per_shift) == len(production)
    assert min(per_shift.values()) > 1


def test_production_and_its_inspection_name_the_same_work_order():
    """PRODUCTION_ENTRY and QUALITY_ENTRY are each joined back to WORK_ORDER
    independently -- crud/analytics.py, calculations/otd.py,
    services/plan_vs_actual_service.py, routes/my_shift.py -- so a shift whose
    two rows point at different orders makes those views disagree about what
    was being run. They share the (client_id, at) key because they describe
    one shift, and that key is unique per (line, shift, day)."""
    events = _gen()
    inspected = {(e.client_id, e.at): e.work_order_id for e in events if isinstance(e, QualityInspected)}
    production = [e for e in events if isinstance(e, ProductionRecorded)]

    assert inspected, "fixture produced no inspections; the comparison below would be vacuous"
    linked = 0
    for e in production:
        if (e.client_id, e.at) not in inspected:
            # No order had been received yet on that day; the column is
            # nullable and inventing an id would be worse.
            assert e.work_order_id is None
            continue
        assert e.work_order_id == inspected[(e.client_id, e.at)]
        linked += 1
    assert linked, "no production row was linked to an order; the equality above would be vacuous"


def test_defect_codes_are_always_catalog_codes():
    """Asserted BOTH ways, for the same reason the hold-catalog test below
    gives: membership alone lets a catalog entry the generator never emits sit
    in DEFECT_TYPE_CATALOG as a dead row. It did -- `(li + si + k) % 5` with
    all three indices in {0, 1} reaches 0..3, so STITCH was structurally
    unreachable and FULL/1234 scored MEASURE 3056, FABRIC 3055, STAIN 1021,
    COLOR 1020, STITCH 0. Pointedly, STITCH is the one code the live dataset
    this rebuild replaces had used for all 80 of its rows."""
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    defined: dict = {}
    emitted: dict = {}
    for e in events:
        if isinstance(e, DefectTypeDefined):
            defined.setdefault(e.client_id, set()).add(e.defect_code)
        elif isinstance(e, DefectsFound):
            assert e.defect_code in DEFECT_CODES
            emitted.setdefault(e.client_id, set()).add(e.defect_code)

    assert set(emitted) == {s.client_id for s in SCENARIOS}
    for client_id, codes in emitted.items():
        assert codes == defined[client_id]
        assert codes == set(DEFECT_CODES)


def test_defect_rows_sum_to_the_inspections_total_defect_count():
    """The split across defect_rows_per_inspection rows must conserve the
    total: DHU is derived from QUALITY_ENTRY while the Pareto is derived from
    DEFECT_DETAIL, and a demo where the two disagree is worse than one with no
    breakdown at all.

    FULL, not SMOKE, and keyed off the QUALITY ENTRIES. The predecessor was
    blind twice over and passed against a stream where 28 of 4104 inspections
    claimed a defect and emitted no detail row at all: SMOKE's
    defect_rows_per_inspection == 1 never executes the split branch, and
    iterating the entries that PRODUCED rows can never see an entry that
    produced none. Deleting `remaining -= count` from the emitter corrupted
    every one of the 4104 entries and the old guard still reported green.

    The single-defect case gets its own coverage assertion because it is the
    exact boundary that broke: at defective == 1 the non-last row draws
    1 // 2 == 0, and a `break` there left before the row that owed the
    remainder."""
    totals: dict = {}
    per_entry: dict = {}
    for e in generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF):
        if isinstance(e, QualityInspected):
            totals[e.quality_entry_id] = e.total_defects_count
        elif isinstance(e, DefectsFound):
            per_entry[e.quality_entry_id] = per_entry.get(e.quality_entry_id, 0) + e.defect_count
    assert FULL.defect_rows_per_inspection >= 2, "profile does not exercise the split; the assertions below are weaker"
    assert totals, "fixture produced no inspections; the comparison below would be vacuous"
    assert any(t == 1 for t in totals.values()), "no single-defect inspection in the fixture; the broken case is absent"
    assert any(t > 1 for t in totals.values()), "no multi-defect inspection in the fixture; the split never runs"
    for qe_id, total in totals.items():
        assert per_entry.get(qe_id, 0) == total, qe_id


def test_downtime_root_causes_come_from_the_live_vocabulary():
    checked = 0
    for e in _gen():
        if isinstance(e, DowntimeLogged):
            assert e.root_cause_category in ROOT_CAUSES
            checked += 1
    assert checked, "fixture produced no downtime; the assertion above would be vacuous"


def test_work_orders_carry_a_required_date_after_receipt():
    orders = [e for e in _gen() if isinstance(e, WorkOrderReceived)]

    assert orders
    for e in orders:
        assert e.required_date > e.at


def test_some_work_orders_carry_no_priority():
    """Spec section 3 decision 6 excludes priority-less orders from the
    priority-adherence denominator and publishes their share as a coverage
    figure. A dataset where every order has a priority cannot demonstrate that
    the exclusion works -- and one where none does cannot demonstrate the
    metric."""
    orders = [e for e in generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF) if isinstance(e, WorkOrderReceived)]

    assert orders
    without = [e for e in orders if e.priority is None]
    assert without
    assert len(without) < len(orders)


def test_the_six_users_are_emitted_once_each_with_their_grants():
    """Compared as multisets and as (user, client) PAIRS, not as counts.
    Counting alone passes a stream that emits one user twice and skips
    another, and passes grants that name the wrong tenant entirely -- which is
    the failure that would actually matter, since a grant is what
    USER_CLIENT_ASSIGNMENT is built from and what the scope resolver reads."""
    events = _gen()
    users = [e.user_id for e in events if isinstance(e, UserCreated)]
    grants = [(e.user_id, e.client_id) for e in events if isinstance(e, ClientAccessGranted)]

    assert sorted(users) == sorted(u.user_id for u in USERS)
    assert sorted(grants) == sorted((u.user_id, cid) for u in USERS for cid in u.client_ids)
    # is_primary marks the FIRST client of a multi-client user, so exactly one
    # grant per granted user carries it.
    primary = [(e.user_id, e.client_id) for e in events if isinstance(e, ClientAccessGranted) and e.is_primary]
    assert sorted(primary) == sorted((u.user_id, u.client_ids[0]) for u in USERS if u.client_ids)


def test_a_single_client_subset_grants_no_access_to_a_client_it_never_creates():
    """generate()'s contract is a self-consistent stream for the scenarios it
    was actually GIVEN, not just for the full SCENARIOS tuple every other
    test in this file passes -- _gen() and every direct generate(SCENARIOS,
    ...) call above make the known_client_ids filter in
    generator._generate_platform a no-op, so none of them can detect its
    removal. Without that filter, this single-client call would still emit
    ClientAccessGranted rows quoting DEMO-HOURLY, DEMO-HYBRID, and
    SAMPLE_REF -- clients this call never creates -- and materializing the
    stream would hit the foreign key those grants can't satisfy.

    Called directly against generate(), not routed through cli.py: cli.py's
    seed() applies its own redundant client_id filter to the events
    generate() returns (see its docstring), which would silently mask a
    reverted fix here and keep a CLI-level subset test green regardless."""
    subset = tuple(s for s in SCENARIOS if s.client_id == "DEMO-PIECE")
    events = generate(subset, SMOKE, seed=1234, as_of=AS_OF)
    grants = [e for e in events if isinstance(e, ClientAccessGranted)]

    assert grants, "fixture produced no grants; the assertion below would be vacuous"
    for e in grants:
        assert e.client_id == "DEMO-PIECE"


def test_a_subset_excluding_a_leader_granted_client_still_grants_no_leak():
    """USR-DEMO-LEADER is granted all three DEMO-* clients (DEMO-PIECE,
    DEMO-HOURLY, DEMO-HYBRID) -- the widest client_ids of any user in USERS.
    Generating DEMO-HOURLY alone exercises the leak path the single-client
    test above cannot reach: TWO of the leader's three declared grants
    (DEMO-PIECE, DEMO-HYBRID) name clients this call never creates, so if
    known_client_ids stopped filtering, this is exactly where a dangling
    grant -- and the materializer's foreign-key violation -- would appear.

    Also on the record here, not asserted as correct (see generator.py's
    known_client_ids docstring -- a pre-existing quirk, out of scope for this
    task): is_primary is computed as `cid == spec.client_ids[0]` against the
    user's FULL declared client list, not the subset being generated. The
    leader's first client is DEMO-PIECE, which this subset excludes, so the
    leader's one surviving grant (DEMO-HOURLY) never carries is_primary=True
    -- this stream contains zero is_primary rows for USR-DEMO-LEADER. No
    database constraint enforces exactly-one-primary, so this does not raise;
    it is observed and recorded here rather than fixed."""
    subset = tuple(s for s in SCENARIOS if s.client_id == "DEMO-HOURLY")
    events = generate(subset, SMOKE, seed=1234, as_of=AS_OF)
    grants = [e for e in events if isinstance(e, ClientAccessGranted)]

    assert grants, "fixture produced no grants; the assertion below would be vacuous"
    for e in grants:
        assert e.client_id == "DEMO-HOURLY"

    leader_grants = [e for e in grants if e.user_id == "USR-DEMO-LEADER"]
    assert leader_grants, "leader must still be granted DEMO-HOURLY in this subset"
    # Pre-existing quirk (see docstring above): is_primary can never be True
    # here because the leader's declared first client (DEMO-PIECE) is outside
    # this subset. Recorded, not fixed.
    assert not any(e.is_primary for e in leader_grants)


def test_a_client_subset_stream_materializes_without_a_foreign_key_violation(seed_engine):
    """The two tests above prove the no-leaked-grant property directly on the
    stream; this is the end-to-end proof they approximate -- that a subset
    stream is not just internally self-describing but actually insertable
    into a real, foreign-key-enforcing database (seed_engine: Alembic-built,
    PRAGMA foreign_keys=ON). Cheap: SMOKE is a 14-day profile and this
    materializes a single client. materialize() raising here -- the FK
    violation the known_client_ids filter exists to prevent -- is exactly the
    failure this test module exists to catch before a real seed run does."""
    subset = tuple(s for s in SCENARIOS if s.client_id == "DEMO-HOURLY")
    events = generate(subset, SMOKE, seed=1234, as_of=AS_OF)

    with seed_engine.begin() as conn:
        counts = materialize(conn, events, SMOKE)

    assert counts["USER_CLIENT_ASSIGNMENT"] > 0


def test_production_is_attributed_to_a_platform_scoped_user():
    """entered_by is a foreign key to USER, so the old seeder's bare string
    left the "who entered this" column pointing at nobody -- but resolving is
    only half of it. ONE user is attributed every client's production, so a
    tenant-scoped user puts "Demo Supervisor" (granted DEMO-PIECE alone) on
    SAMPLE_REF's rows. Not an FK error; in a product whose client-scope
    authorization was just made uniform, it reads as a tenant-isolation bug.

    So: the id must resolve to a user the stream created, that user must be
    granted no client at all, and every production row must name the same one
    -- the previous version asserted only the first of the three."""
    scoped = {u.user_id: u.client_ids for u in USERS}
    created = set()
    attributed = set()
    for e in _gen():
        if isinstance(e, UserCreated):
            created.add(e.user_id)
        elif isinstance(e, ProductionRecorded):
            assert e.entered_by in created
            attributed.add(e.entered_by)
    assert len(attributed) == 1, attributed
    entered_by = attributed.pop()
    assert scoped[entered_by] == ()


def test_hold_reasons_and_statuses_quote_the_clients_own_catalog():
    """HOLD_REASON_CATALOG and HOLD_STATUS_CATALOG are new in this commit and
    both are foreign keys in the target schema: a hold opened on a reason no
    catalog carries, or advanced to a status no catalog declares, fails the
    insert. Keyed on (client_id, code) because the catalogs are per client, so
    quoting another tenant's code is the same defect as quoting none.

    Asserted BOTH ways -- every emitted value is a catalog code, and every
    catalog code is emitted. Membership alone degrades silently: SMOKE/1234
    produces exactly one hold with one transition, so it satisfies membership
    while touching 1 of 3 reasons and 1 of 4 statuses, and an off-catalog value
    on any other branch would sail through. FULL reaches all seven, and the
    equality is what keeps it that way -- including against a catalog that
    grows an entry the generator never uses, which is a dead row in the demo."""
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    reasons: set = set()
    statuses: set = set()
    seen_reasons: set = set()
    seen_statuses: set = set()
    for e in events:
        if isinstance(e, HoldReasonDefined):
            reasons.add((e.client_id, e.reason_code))
        elif isinstance(e, HoldStatusDefined):
            statuses.add((e.client_id, e.status_code))
        elif isinstance(e, HoldOpened):
            assert (e.client_id, e.reason_category) in reasons
            seen_reasons.add(e.reason_category)
        elif isinstance(e, HoldStatusChanged):
            assert (e.client_id, e.to_status) in statuses
            seen_statuses.add(e.to_status)
    assert seen_reasons == {code for code, _, _ in HOLD_REASONS}
    assert seen_statuses == {code for code, _, _ in HOLD_STATUSES}
