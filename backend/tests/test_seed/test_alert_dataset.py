"""The alert board, asserted against a FULL seeded database.

The dashboard groups by severity and by category and the workflow moves rows
between three statuses, so a board holding one row demonstrates a list rather
than a board. These pin that all three axes are actually populated, and that
the alerts point at real work.
"""

from datetime import date

import pytest
from sqlalchemy import text

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


def test_the_board_spans_every_axis_the_dashboard_groups_by(full_db):
    with full_db.begin() as conn:
        severities = {r[0] for r in conn.execute(text("SELECT DISTINCT severity FROM ALERT"))}
        categories = {r[0] for r in conn.execute(text("SELECT DISTINCT category FROM ALERT"))}
        statuses = {r[0] for r in conn.execute(text("SELECT DISTINCT status FROM ALERT"))}

    # `by_severity` and `by_category` are the dashboard's two groupings; a
    # single-valued column renders one bar and proves nothing about either.
    assert len(severities) >= 3, f"only {sorted(severities)} severities seeded"
    assert len(categories) >= 3, f"only {sorted(categories)} categories seeded"
    # All three, so acknowledge and resolve are both demonstrable.
    assert statuses == {"active", "acknowledged", "resolved"}, sorted(statuses)


def test_no_alert_points_at_a_work_order_that_does_not_exist(full_db):
    """A dangling link is worse than no link: the row renders and goes nowhere."""
    with full_db.begin() as conn:
        dangling = conn.execute(
            text(
                "SELECT COUNT(*) FROM ALERT a WHERE a.work_order_id IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM WORK_ORDER w WHERE w.work_order_id = a.work_order_id)"
            )
        ).scalar_one()
    assert dangling == 0


def test_every_alert_history_row_hangs_off_a_real_alert(full_db):
    with full_db.begin() as conn:
        orphans = conn.execute(
            text(
                "SELECT COUNT(*) FROM ALERT_HISTORY h "
                "WHERE NOT EXISTS (SELECT 1 FROM ALERT a WHERE a.alert_id = h.alert_id)"
            )
        ).scalar_one()
    assert orphans == 0


def test_the_accuracy_ledger_records_both_outcomes(full_db):
    """A history where every prediction was right shows a column, not a track
    record."""
    with full_db.begin() as conn:
        accurate, total = conn.execute(
            text("SELECT SUM(CASE WHEN was_accurate THEN 1 ELSE 0 END), COUNT(*) FROM ALERT_HISTORY")
        ).first()
    assert total > 0
    assert 0 < accurate < total, f"{accurate}/{total} accurate -- one outcome never occurs"


def test_a_disabled_alert_config_exists(full_db):
    """A configuration screen where every row is enabled never shows what a
    disabled row looks like."""
    with full_db.begin() as conn:
        disabled = conn.execute(text("SELECT COUNT(*) FROM ALERT_CONFIG WHERE enabled = 0")).scalar_one()
        enabled = conn.execute(text("SELECT COUNT(*) FROM ALERT_CONFIG WHERE enabled = 1")).scalar_one()
    assert disabled > 0 and enabled > 0


def test_every_seeded_row_survives_the_schema_its_endpoint_returns(full_db):
    """ALERT_CONFIG.alert_type is a bare String(30) with no DB constraint, so a
    value outside AlertCategory inserts cleanly and only raises when the
    endpoint serializes it back. `hold_approval` -- the kpi_key of the alert
    rows, which ALERT_CONFIG has no column for -- shipped in that field and
    turned the paramless-GET smoke test red with a 500 rather than failing
    anything here. Validating the seeded rows against the response models
    catches that class where it is introduced.
    """
    from sqlalchemy.orm import Session

    from backend.orm.alert import Alert, AlertConfig
    from backend.schemas.alert import AlertConfigResponse, AlertResponse

    broken = []
    with Session(bind=full_db) as session:
        for model, schema in ((AlertConfig, AlertConfigResponse), (Alert, AlertResponse)):
            rows = session.query(model).all()
            assert rows, f"no {model.__tablename__} rows seeded"
            for row in rows:
                try:
                    schema.model_validate(row, from_attributes=True)
                except Exception as exc:
                    fields = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}={e.get('input')!r}" for e in exc.errors())
                    broken.append(f"{model.__tablename__}: {fields}")
    assert not broken, "seeded rows the endpoint cannot serialize:\n  " + "\n  ".join(sorted(set(broken)))
