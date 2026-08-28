"""Forward side of the registry: every declared model is actually hidden.

The failure mode this exists to catch is a soft delete that does not hide
anything. Declaring a table in ``AUTO_FILTERED_TABLES`` is a claim; each test
here spends a real row to check the claim on the read shapes production
actually uses — object reads, column reads, aggregates, 2.0-style ``select()``,
and primary-key lookups — not just the one that motivated the change.

Every case is non-vacuous: it asserts the row is visible first, so a filter
that hid everything (or a fixture that built nothing) would fail rather than
pass.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.db.soft_delete_filter import INCLUDE_INACTIVE, auto_filtered_models, include_inactive
from backend.db.soft_delete_registry import AUTO_FILTERED_TABLES
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.soft_delete_rows import PK_ATTR, build_transaction_rows

TABLES = sorted(AUTO_FILTERED_TABLES)


@pytest.fixture(scope="function")
def rows():
    engine = clone_template_engine()
    session = sessionmaker(bind=engine)()
    try:
        yield session, build_transaction_rows(session)
    finally:
        session.close()
        engine.dispose()


def _model_for(table: str):
    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table:
            return mapper.class_
    raise AssertionError(f"no mapped class for {table}")


def _read_shapes(session, model, pk_attr, pk_value):
    """Every ORM read shape that must agree about whether the row is there.

    ``session.get`` runs on a *second* session bound to the same engine, which
    is what a request actually sees: FastAPI's ``get_db`` hands every request a
    fresh session, so the identity map is empty. Reusing this session would
    instead exercise the documented refresh exemption — pinned separately in
    ``test_identity_map_refresh_is_the_one_documented_exemption``.
    """
    pk_col = getattr(model, pk_attr)
    fresh = sessionmaker(bind=session.get_bind())()
    try:
        by_pk = [pk_value] if fresh.get(model, pk_value) is not None else []
    finally:
        fresh.close()
    return {
        "query(Model)": [getattr(o, pk_attr) for o in session.query(model).all()],
        "query(Model.pk)": [r[0] for r in session.query(pk_col).all()],
        "select(Model)": [getattr(o, pk_attr) for o in session.execute(select(model)).scalars().all()],
        "select(Model.pk)": [r[0] for r in session.execute(select(pk_col)).all()],
        "count(pk == target)": [pk_value] * session.query(func.count(pk_col)).filter(pk_col == pk_value).scalar(),
        "session.get (fresh session)": by_pk,
    }


@pytest.mark.parametrize("table", TABLES)
def test_soft_deleted_row_vanishes_from_every_orm_read_shape(rows, table):
    session, built = rows
    model = _model_for(table)
    pk_attr = PK_ATTR[table]
    pk_value = getattr(built[table], pk_attr)

    for shape, visible in _read_shapes(session, model, pk_attr, pk_value).items():
        assert pk_value in visible, f"{table}: fixture row missing from {shape} before delete"

    built[table].is_active = False
    session.commit()

    for shape, visible in _read_shapes(session, model, pk_attr, pk_value).items():
        assert pk_value not in visible, f"{table}: soft-deleted row still visible via {shape}"


@pytest.mark.parametrize("table", TABLES)
def test_soft_deleted_row_stays_hidden_in_a_fresh_session(rows, table):
    """Hiding is a property of the data, not of the session that deleted it."""
    session, built = rows
    model = _model_for(table)
    pk_attr = PK_ATTR[table]
    pk_value = getattr(built[table], pk_attr)

    built[table].is_active = False
    session.commit()

    other = sessionmaker(bind=session.get_bind())()
    try:
        assert other.get(model, pk_value) is None
    finally:
        other.close()


@pytest.mark.parametrize("table", TABLES)
def test_inactive_rows_are_reachable_through_the_explicit_opt_in(rows, table):
    """Soft delete preserves the audit record; it must remain readable on request."""
    session, built = rows
    model = _model_for(table)
    pk_attr = PK_ATTR[table]
    pk_col = getattr(model, pk_attr)
    pk_value = getattr(built[table], pk_attr)

    built[table].is_active = False
    session.commit()

    via_option = [r[0] for r in session.query(pk_col).execution_options(**{INCLUDE_INACTIVE: True}).all()]
    assert pk_value in via_option

    with include_inactive(session):
        via_context = [r[0] for r in session.query(pk_col).all()]
    assert pk_value in via_context

    assert pk_value not in [r[0] for r in session.query(pk_col).all()]


def test_the_filter_is_scoped_and_does_not_touch_undeclared_models(rows):
    """S1 is deliberately not global: EMPLOYEE keeps its ad-hoc behaviour.

    A global filter on EMPLOYEE would hide a departed worker from every join,
    including the attendance and production rows that legitimately belong to
    them — moving KPIs silently. That change is S1b's, under its own
    verification, so it must NOT arrive as a side effect of this one.
    """
    from backend.orm.employee import Employee

    session, built = rows
    employee = built["employee"]
    employee_id = employee.employee_id
    employee.is_active = 0
    session.commit()

    # A fresh session, i.e. an empty identity map. Reading it back through this
    # session would hit the documented refresh exemption and pass even if
    # EMPLOYEE *were* auto-filtered — a false green this test must not have.
    fresh = sessionmaker(bind=session.get_bind())()
    try:
        assert fresh.get(Employee, employee_id) is not None
        assert employee_id in [r[0] for r in fresh.query(Employee.employee_id).all()]
    finally:
        fresh.close()


def test_installed_filter_covers_exactly_the_declared_tables():
    installed = sorted(model.__tablename__ for model in auto_filtered_models())
    assert installed == TABLES


@pytest.mark.parametrize("table", TABLES)
def test_identity_map_refresh_is_the_one_documented_exemption(rows, table):
    """Attribute refreshes are exempt on purpose, and only within one session.

    ``apply_active_row_filter`` skips ``is_column_load`` executions so that
    ``db.refresh(entity)`` keeps working on a row that was just soft-deleted —
    without the exemption every delete path that refreshes would raise instead
    of returning 204. The visible consequence is that ``session.get`` on an
    object still in *that same* session's identity map issues a refresh and
    returns it. Requests never see this: FastAPI hands each one a new session.

    Pinned so the exemption stays a decision. Removing the ``is_column_load``
    skip flips this test, which is the prompt to deal with ``db.refresh``.
    """
    session, built = rows
    model = _model_for(table)
    pk_attr = PK_ATTR[table]
    pk_value = getattr(built[table], pk_attr)

    assert session.get(model, pk_value) is not None  # loaded into the identity map

    built[table].is_active = False
    session.commit()

    assert session.get(model, pk_value) is not None  # refresh exemption, same session

    session.expunge_all()
    assert session.get(model, pk_value) is None  # empty identity map -> filtered


# ---------------------------------------------------------------------------
# Cascade: normalised by refusal, not by hiding children.
# ---------------------------------------------------------------------------


def _hideable_dependents(parent_table: str):
    """(child table, child FK column, parent PK column) for every dependent that
    HAS an is_active column — i.e. every one that can be, and therefore must be,
    hidden with its parent.

    Read straight off Base.metadata. It deliberately consults neither
    CHILD_CLASSIFICATION nor visible_child_blockers: this is the check on those,
    and a check that asks the implementation what to expect proves nothing. The
    previous version of this test did exactly that and passed with the entire
    409 mechanism disabled.

    Dependents WITHOUT an is_active column are excluded because they cannot be
    hidden and have no endpoint of their own — they are reachable only through
    the parent, which is now invisible.
    """
    out = []
    for table in Base.metadata.sorted_tables:
        if "is_active" not in table.c:
            continue
        for fk in table.foreign_keys:
            if fk.column.table.name == parent_table:
                out.append((table.name, fk.parent.name, fk.column.name))
    return sorted(out)


def _visible_referencing_rows(session, parent_table, parent_entity):
    """(child table, row) for every still-visible row pointing at this parent."""
    found = []
    for child_table, fk_column, parent_column in _hideable_dependents(parent_table):
        child_model = _model_for(child_table)
        parent_value = getattr(parent_entity, parent_column, None)
        if parent_value is None:
            continue
        rows = session.query(child_model).filter(getattr(child_model, fk_column) == parent_value).all()
        found.extend((child_table, row) for row in rows)
    return found


def _visible_referencing_count(session, parent_table, parent_entity):
    return len(_visible_referencing_rows(session, parent_table, parent_entity))


def _tenant_of(row):
    return getattr(row, "client_id", None) or getattr(row, "client_id_fk", None)


@pytest.mark.parametrize("table", TABLES)
def test_no_visible_row_ever_references_a_hidden_parent(rows, table):
    """The invariant itself, computed independently of the code under test.

    Either mechanism may satisfy it — the delete is refused (409) and the parent
    stays visible, or the delete succeeds and every hideable child went with it.
    What must never happen is a hidden parent with a visible child.

    Both branches are non-vacuous: the refusal branch asserts a blocker really
    was there, the success branch asserts the parent really is gone. A
    ``visible_child_blockers`` that returned ``{}`` unconditionally would send
    WORK_ORDER down the success branch with five visible children and fail.
    """
    from backend.db.soft_delete_service import soft_delete_record
    from fastapi import HTTPException

    session, built = rows
    entity = built[table]
    pk_attr = PK_ATTR[table]
    pk_value = getattr(entity, pk_attr)
    model = _model_for(table)

    before = _visible_referencing_count(session, table, entity)

    try:
        assert soft_delete_record(session, entity) is True
        session.commit()
    except HTTPException as exc:
        assert exc.status_code == 409
        session.rollback()
        # Refused: the parent must still be there, and something must really
        # have been blocking it.
        assert session.query(model).filter(getattr(model, pk_attr) == pk_value).count() == 1
        assert before > 0
        return

    session.expunge_all()
    entity = session.query(model).filter(getattr(model, pk_attr) == pk_value)
    assert entity.count() == 0, f"{table} reports deleted but is still visible"
    with include_inactive(session):
        hidden = session.query(model).filter(getattr(model, pk_attr) == pk_value).one()
    survivors = _visible_referencing_rows(session, table, hidden)
    # The one declared exception: a child with NO tenant of its own is visible
    # org-wide (TENANT_SCOPED_CASCADE) and is not one tenant's row to hide. It is
    # asserted here as a property of the data — tenant-less — not by naming a
    # table, so widening the exception to a tenant-scoped row fails.
    offenders = [f"{t}:{getattr(row, 'alert_id', row)}" for t, row in survivors if _tenant_of(row) is not None]
    assert offenders == [], f"{table} {pk_value} is hidden but tenant-scoped rows still reference it: {offenders}"


def test_a_successful_cascade_leaves_the_join_and_the_plain_read_agreeing(rows):
    """The symptom, asserted as the property its name claims.

    A still-active production entry used to drop out of the analytics KPI
    purely because that query inner-joins its parent. The earlier version of
    this test only proved the 409 fires, which is not the same statement — and
    review showed the title was false, because a child could still be attached
    to an already-hidden parent afterwards (closed separately in
    backend/db/soft_delete_writes.py and covered end to end in
    tests/test_routes/test_hidden_parent_writes.py).

    Here the check is run across a DELETE that actually succeeds, cascading a
    derived alert, so the agreement is proved after a real hide rather than
    after a refusal.
    """
    from backend.db.soft_delete_service import soft_delete_record
    from backend.orm.alert import Alert
    from backend.orm.production_entry import ProductionEntry
    from backend.orm.work_order import WorkOrder

    session, built = rows
    target = built["WORK_ORDER_alert_only"]
    alert_id = built["ALERT_only"].alert_id

    def plain():
        return session.query(func.count(ProductionEntry.production_entry_id)).scalar()

    def joined():
        return (
            session.query(func.count(ProductionEntry.production_entry_id))
            .join(WorkOrder, ProductionEntry.work_order_id == WorkOrder.work_order_id)
            .scalar()
        )

    assert plain() == joined()

    assert soft_delete_record(session, target) is True
    session.commit()
    session.expunge_all()

    # the cascade really happened...
    assert session.query(Alert).filter(Alert.alert_id == alert_id).count() == 0
    # ...and the two readings of the same rows still agree
    assert plain() == joined()


def test_bypassing_the_service_still_produces_the_old_incoherence(rows):
    """Why the service is the ONLY entry point, and why that is gated.

    Setting is_active by hand skips the blocking check, and the three-answer
    incoherence comes straight back: the job stays visible, while the same
    production row disappears from the inner-join analytics read. This is the
    state test_every_auto_filtered_delete_goes_through_the_service exists to
    keep unreachable — it is not a bug in the filter, it is the reason the
    filter alone was never enough.
    """
    from backend.orm.job import Job
    from backend.orm.production_entry import ProductionEntry
    from backend.orm.work_order import WorkOrder

    session, built = rows
    work_order = built["WORK_ORDER"]

    def joined_production_count():
        return (
            session.query(func.count(ProductionEntry.production_entry_id))
            .join(WorkOrder, ProductionEntry.work_order_id == WorkOrder.work_order_id)
            .scalar()
        )

    assert joined_production_count() == 1
    assert session.query(func.count(Job.job_id)).scalar() == 1

    work_order.is_active = False  # deliberately NOT soft_delete_record
    session.commit()
    session.expunge_all()

    assert session.query(func.count(Job.job_id)).scalar() == 1  # child still visible
    assert joined_production_count() == 0  # same row, gone from the joined read


def test_the_fixture_gives_the_invariant_something_to_prove(rows):
    """Anti-vacuity for the parametrized invariant above.

    That guard is only meaningful for parents that actually have hideable
    children in the fixture; for a childless one both branches are trivially
    satisfied. If the fixture ever stopped building a parent with children, all
    twelve parametrisations would pass while proving nothing — so assert here
    that at least one of them is a real case, and name how many.
    """
    session, built = rows
    with_children = {
        table: _visible_referencing_count(session, table, built[table])
        for table in TABLES
        if _visible_referencing_count(session, table, built[table]) > 0
    }
    assert with_children, "no fixture parent has hideable children; the invariant guard is vacuous"
    assert with_children["WORK_ORDER"] >= 5


def test_a_delete_cascades_a_tenant_alert_but_spares_the_system_wide_one(rows):
    """N6: one tenant's delete must not remove a row the whole org can see.

    routes/alerts/crud.py shows alerts with client_id IS NULL to every tenant,
    on both its scope branch and its explicit-client_id branch. Cascading those
    would have let tenant A's work-order delete hide a row tenant B was reading.

    The tenant-scoped alert on the SAME work order is still cascaded, so this is
    not the cascade being switched off — it is being confined to what the parent
    actually owns.
    """
    from backend.db.soft_delete_service import soft_delete_record
    from backend.orm.alert import Alert

    session, built = rows
    target = built["WORK_ORDER_alert_only"]
    tenant_alert = built["ALERT_only"].alert_id
    system_alert = built["ALERT_system_wide"].alert_id

    assert soft_delete_record(session, target) is True
    session.commit()
    session.expunge_all()

    assert session.query(Alert).filter(Alert.alert_id == tenant_alert).count() == 0
    assert session.query(Alert).filter(Alert.alert_id == system_alert).count() == 1
    assert session.query(Alert).filter(Alert.alert_id == system_alert).one().is_active is True


def test_the_only_survivors_of_a_cascade_are_tenant_less(rows):
    """The carve-out stated as the invariant's single exception, and bounded.

    Non-vacuous at both ends: two rows reference the parent before, exactly one
    survives, and that one has no tenant.
    """
    from backend.db.soft_delete_service import soft_delete_record
    from backend.orm.work_order import WorkOrder

    session, built = rows
    target = built["WORK_ORDER_alert_only"]
    pk_value = target.work_order_id

    assert _visible_referencing_count(session, "WORK_ORDER", target) == 2

    assert soft_delete_record(session, target) is True
    session.commit()
    session.expunge_all()

    with include_inactive(session):
        hidden = session.query(WorkOrder).filter(WorkOrder.work_order_id == pk_value).one()
    survivors = _visible_referencing_rows(session, "WORK_ORDER", hidden)
    assert len(survivors) == 1
    assert _tenant_of(survivors[0][1]) is None
