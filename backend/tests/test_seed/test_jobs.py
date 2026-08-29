"""The routing: JOB rows, and the entries that point at them.

Six `GET /api/jobs/{job_id}/*` routes were unreachable by the contract
harness because JOB had zero seeded rows. Five of the six read
PRODUCTION_ENTRY / QUALITY_ENTRY by `job_id` and never by `work_order_id`
(backend/routes/jobs.py), so seeding JOB alone would have unblocked them into
answering "no entries found" -- which is why the shift emitter stamps the
column too, and why half of what is asserted here is about the entries rather
than about the jobs.

The routing itself is INVENTED (seed/scenarios.py's banner says so at the
definition). What is NOT invented is its arithmetic: planned_hours decomposes
the same labor content the platform's one efficiency formula computes,
`(units * ideal_cycle_time) / (employees * scheduled_hours)`, so a work
order's jobs and the efficiency reading beside them cannot disagree.
"""

from dataclasses import fields
from datetime import date

import pytest
from sqlalchemy import func, select

from backend.database import Base
from backend.seed import events as ev
from backend.seed.cli import seed
from backend.seed.emitters_operations import WORK_ORDER_FLOW, job_id_for, operations_completed
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import IDEAL_CYCLE_TIME_HOURS, ROUTING, SCENARIOS, SCRAP_UNITS_PER_HUNDRED
from backend.tests.test_seed._reset_row_builders import _insert_job

AS_OF = date(2026, 8, 18)


@pytest.fixture(scope="module")
def events():
    return generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)


def _of(events, cls):
    return [e for e in events if isinstance(e, cls)]


def _furthest_status(events):
    """work_order_id -> how far along WORK_ORDER_FLOW its chain actually got."""
    depth = {}
    for e in _of(events, ev.WorkOrderStatusChanged):
        reached = WORK_ORDER_FLOW.index(e.to_status) + 1
        depth[e.work_order_id] = max(depth.get(e.work_order_id, 0), reached)
    return depth


def test_the_seeded_cycle_time_is_the_one_the_application_resolves():
    """`IDEAL_CYCLE_TIME_HOURS` is a duplicated literal -- backend/seed/ may
    not import backend.calculations (test_purity.py) -- so nothing but this
    test ties it to the value it claims to mirror.

    Seeded PRODUCT rows carry no ideal_cycle_time, so every seeded production
    entry falls through to DEFAULT_CYCLE_TIME. If that constant is retuned and
    this one is not, every JOB.planned_hours in the demo silently stops
    matching the efficiency figure shown next to it.
    """
    from backend.calculations.efficiency import DEFAULT_CYCLE_TIME

    assert IDEAL_CYCLE_TIME_HOURS == float(DEFAULT_CYCLE_TIME)


def test_a_work_orders_routing_decomposes_its_labor_content(events):
    """The routing SPLITS the order's labor content; it does not multiply it.

    Dropping the `/ len(ROUTING)` from planned_hours leaves every individual
    row looking plausible while the order as a whole claims four times the
    hours the efficiency formula would earn for the same units. The tolerance
    is the per-row rounding to 2dp, nothing more.
    """
    planned_by_order = {e.work_order_id: e.planned_quantity for e in _of(events, ev.WorkOrderReceived)}
    hours_by_order = {}
    for job in _of(events, ev.JobDefined):
        hours_by_order.setdefault(job.work_order_id, 0.0)
        hours_by_order[job.work_order_id] += job.planned_hours

    assert hours_by_order, "no JobDefined events: every assertion below would be vacuous"
    for work_order_id, hours in hours_by_order.items():
        earned = planned_by_order[work_order_id] * IDEAL_CYCLE_TIME_HOURS
        # Half a cent of rounding per row is the ONLY drift allowed: each
        # planned_hours is rounded to the column's 2dp, so n rows can lose at
        # most n * 0.005. Compared after rounding, because binary floats put
        # the exact boundary case (4 x 15.625 -> 4 x 15.62) a 1e-14 above it.
        assert round(abs(hours - earned), 2) <= len(ROUTING) * 0.005, work_order_id


def test_every_order_gets_the_whole_routing(events):
    """One JOB per (order, routing step), and the sequence numbers are the
    routing's own 1..n -- an off-by-one in the `enumerate(..., start=1)` would
    otherwise surface only as a wrong-looking number on a screen."""
    by_order = {}
    for job in _of(events, ev.JobDefined):
        by_order.setdefault(job.work_order_id, []).append(job)

    orders = {e.work_order_id for e in _of(events, ev.WorkOrderReceived)}
    assert set(by_order) == orders
    for work_order_id, jobs in by_order.items():
        assert [j.sequence_number for j in jobs] == list(range(1, len(ROUTING) + 1)), work_order_id
        assert [j.operation_code for j in jobs] == [code for code, _name in ROUTING]
        assert [j.job_id for j in jobs] == [job_id_for(work_order_id, n) for n in range(1, len(ROUTING) + 1)]


def test_a_job_never_claims_work_its_order_has_not_reached(events):
    """The routing's progress is DERIVED from the order's own chain. An order
    still sitting at RECEIVED or RELEASED whose jobs report finished units is
    the internal contradiction this rebuild exists to remove -- and it is what
    `operations_completed`'s two thresholds prevent.
    """
    depth = _furthest_status(events)
    in_progress = WORK_ORDER_FLOW.index("IN_PROGRESS") + 1
    completed = WORK_ORDER_FLOW.index("COMPLETED") + 1
    seen_untouched = seen_finished = False

    for job in _of(events, ev.JobDefined):
        reached = depth[job.work_order_id]
        if reached < in_progress:
            seen_untouched = True
            assert job.completed_quantity == 0, job.job_id
            assert job.is_completed is False
            assert job.completed_date is None
        if reached >= completed:
            seen_finished = True
            assert job.is_completed is True, job.job_id
            assert job.completed_quantity == job.planned_quantity

    assert seen_untouched and seen_finished, "one side of the branch never occurred; the test proves half of itself"


def test_a_finished_step_scraps_units_so_yield_is_not_a_constant_hundred(events):
    """`quantity_scrapped` is the whole numerator of
    GET /api/jobs/{job_id}/yield. At SCRAP_UNITS_PER_HUNDRED = 0 every job in
    the demo reports exactly 100.00% and the metric demonstrates nothing.
    """
    finished = [j for j in _of(events, ev.JobDefined) if j.completed_quantity > 0]

    assert finished
    assert all(j.quantity_scrapped > 0 for j in finished)
    assert all(j.quantity_scrapped < j.completed_quantity for j in finished)
    # /yield and /kpi-summary disagree by design when scrap exceeds completed
    # (fpy_rty.py:615 does not clamp, :104 does), so the seeder must never
    # produce that row -- asserted above, and the rate is what guarantees it.
    assert SCRAP_UNITS_PER_HUNDRED < 100


def test_a_completion_date_never_claims_a_day_that_has_not_happened(events):
    """Same clamp the delivery date takes: the furthest transition day can sit
    past as_of (the chain is generated forward and then the stream is clamped),
    so an unclamped completed_date would date a finished operation into the
    future."""
    finished = [j for j in _of(events, ev.JobDefined) if j.is_completed]

    assert finished
    for job in finished:
        assert job.completed_date is not None
        assert job.completed_date.date() <= AS_OF, job.job_id


def test_every_entry_that_names_an_order_names_one_of_that_orders_jobs(events):
    """The column the routes actually join on.

    PRODUCTION_ENTRY.job_id and QUALITY_ENTRY.job_id are nullable, so dropping
    the stamp is a silent change: the entries still exist, still carry their
    work order, and five of the six routes answer "no entries found for this
    job" with a 200.
    """
    job_ids = {j.job_id for j in _of(events, ev.JobDefined)}
    entries = _of(events, ev.ProductionRecorded) + _of(events, ev.QualityInspected)
    named = [e for e in entries if e.work_order_id is not None]

    assert named
    for entry in named:
        assert entry.job_id in job_ids
        assert entry.job_id.startswith(f"{entry.work_order_id}-OP"), entry.job_id


def test_one_shifts_production_and_inspection_name_the_same_step(events):
    """/kpi-summary unions PRODUCTION_ENTRY and QUALITY_ENTRY for ONE job id.
    A shift whose output and inspection sat on different operations makes that
    single endpoint contradict itself -- efficiency from one step, ppm from
    another."""
    production = {(e.client_id, e.at): e.job_id for e in _of(events, ev.ProductionRecorded)}
    inspected = {(e.client_id, e.at): e.job_id for e in _of(events, ev.QualityInspected)}

    assert inspected
    for key, job_id in inspected.items():
        assert production[key] == job_id


def test_the_routing_costs_the_rng_stream_nothing(monkeypatch):
    """The strongest guard in this module, and the one a reviewer should read
    first.

    Every JOB value is derived from draws the order has already made. A single
    `rng` call added to the routing block would move every subsequent draw for
    every client and shift the FULL-profile narrative pins in
    test_narrative_dataset.py (aged-and-excluded holds == 14, SAMPLE_REF months
    below 80% OTD == 0) -- failures a reader would never trace back to jobs.

    Widening the routing changes how many JobDefined events exist, and
    therefore every `seq` after the first one, so the comparison drops `seq`
    and `job_id` and keeps every value an RNG draw decided. If the routing
    consumed randomness, six steps and four steps could not agree.
    """
    from backend.seed import emitters_operations

    def fingerprint(stream):
        out = []
        for e in stream:
            if isinstance(e, ev.JobDefined):
                continue
            # `seq` and `job_id` are the two fields a wider routing legitimately
            # moves (more events shift every later seq; the rotation picks a
            # different step). Everything else -- every quantity, every date,
            # every category the RNG chose -- must be identical.
            skip = ("seq", "job_id")
            out.append(
                (type(e).__name__,)
                + tuple(getattr(e, f.name) for f in sorted(fields(e), key=lambda f: f.name) if f.name not in skip)
            )
        return out

    four = fingerprint(generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF))
    monkeypatch.setattr(emitters_operations, "ROUTING", ROUTING + (("TEST-A", "A"), ("TEST-B", "B")))
    six = fingerprint(generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF))

    assert four == six


def test_operations_completed_rotates_across_the_routing():
    """Mid-flow orders must not all freeze on the same step: a demo where
    every in-progress order stopped at operation 1 reads as a data artefact.
    Pinned directly on the helper, because the property is invisible in the
    aggregate."""
    in_progress = WORK_ORDER_FLOW.index("IN_PROGRESS") + 1
    reached = {operations_completed(in_progress, i) for i in range(len(ROUTING) * 2)}

    assert reached == set(range(1, len(ROUTING)))
    assert operations_completed(WORK_ORDER_FLOW.index("RELEASED") + 1, 0) == 0
    assert operations_completed(len(WORK_ORDER_FLOW), 0) == len(ROUTING)


def test_the_materialized_rows_carry_the_tenant_column_and_are_visible(seed_engine):
    """JOB's tenant column is `client_id_fk`, one of the three spellings this
    schema uses, and JOB is registered for soft delete -- a row written with
    the wrong column or with is_active left to its server default is invisible
    to every route in backend/routes/jobs.py, which reports it as a 404 on the
    id rather than as a seeding fault."""
    stream = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        counts = materialize(conn, stream, SMOKE)

    job = Base.metadata.tables["JOB"]
    with seed_engine.connect() as conn:
        rows = conn.execute(select(job.c.job_id, job.c.client_id_fk, job.c.is_active, job.c.planned_hours)).all()
        entries = Base.metadata.tables["PRODUCTION_ENTRY"]
        linked = conn.execute(
            select(func.count()).select_from(entries).where(entries.c.job_id.isnot(None))
        ).scalar_one()

    assert counts["JOB"] == len(rows) == len(_of(stream, ev.JobDefined))
    assert all(client_id for _job_id, client_id, _active, _hours in rows)
    assert all(active for _job_id, _client, active, _hours in rows)
    assert all(hours is not None for *_rest, hours in rows)
    assert linked > 0


def test_reset_clears_a_planted_job_and_rewrites_the_seeders_own(seed_engine):
    """The case CHILD_ROW_BUILDERS used to carry for JOB.

    It cannot live there any more -- that map's test asserts the table holds
    zero rows for the client afterwards, which a SEEDED table can never
    satisfy, because --reset re-seeds. The hazard is unchanged though: a JOB
    row is a child of WORK_ORDER, so one left behind RESTRICTs a DELETE inside
    the sweep rather than at CLIENT.
    """
    job = Base.metadata.tables["JOB"]
    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=AS_OF)
    seed(seed_engine, reset=False, **kwargs)
    with seed_engine.begin() as conn:
        _insert_job(conn, "DEMO-PIECE")

    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        planted = conn.execute(
            select(func.count()).select_from(job).where(job.c.job_id == "JOB-DEMO-PIECE")
        ).scalar_one()
        seeded = conn.execute(
            select(func.count()).select_from(job).where(job.c.client_id_fk == "DEMO-PIECE")
        ).scalar_one()

    assert planted == 0
    assert seeded > 0
