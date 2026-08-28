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
    employee.is_active = 0
    session.commit()

    assert session.get(Employee, employee.employee_id) is not None


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
