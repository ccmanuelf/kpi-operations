from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.hold_entry import HoldStatus
from backend.orm.user import User, UserRole


@pytest.fixture
def _bind(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


def _as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_operator_cannot_read_other_clients_trend(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_can_read_own_trend(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-A"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_narrow_to_any_client(_bind, admin_user):
    c = _as(admin_user)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-B"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_cause(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert (
            c.get("/api/kpi/availability/cause", params={"date": "2026-07-14", "client_id": "CLIENT-B"}).status_code
            == 403
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_efficiency_by_shift(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/efficiency/by-shift", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_dashboard(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/dashboard/aggregated", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_defects(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/quality/kpi/defects-by-type", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/quality/kpi/top-defects", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_wip_aging(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/wip-aging", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/kpi/wip-aging/top", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/attendance/kpi/absenteeism", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_thresholds(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi-thresholds", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/hold-catalogs/statuses", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_can_read_own_thresholds_and_catalogs(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi-thresholds", params={"client_id": "CLIENT-A"}).status_code == 200
        assert c.get("/api/hold-catalogs/statuses", params={"client_id": "CLIENT-A"}).status_code == 200
        assert c.get("/api/hold-catalogs/reasons", params={"client_id": "CLIENT-A"}).status_code == 200
        assert c.get("/api/break-times", params={"client_id": "CLIENT-A"}).status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_read_any_clients_thresholds(_bind, admin_user):
    c = _as(admin_user)
    try:
        assert c.get("/api/kpi-thresholds", params={"client_id": "CLIENT-B"}).status_code == 200
        assert c.get("/api/hold-catalogs/statuses", params={"client_id": "CLIENT-B"}).status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_my_shift_scoped_to_own_client(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/my-shift/summary")
        assert r.status_code == 200  # scoped to CLIENT-A only (no cross-tenant rows)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_metric_results_scoped(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        # requesting another client's results is refused (dependency 403s the param)
        assert c.get("/api/metrics/results", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_multi_client_leader_dashboard_quality_not_degraded(_bind, leader_user_multi_client):
    # A multi-client leader with no client_id must not trip the ClientConfig
    # gate into raising HTTPException(400) (which was swallowed and degraded
    # the quality section to a zeroed "Calculation error" payload).
    c = _as(leader_user_multi_client)
    try:
        r = c.get("/api/kpi/dashboard/aggregated")
        assert r.status_code == 200
        quality = r.json()["quality"]
        assert "error" not in quality
        assert quality["opportunities_per_unit"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# Task 8 — Pattern C (missing-scope leaks) + Pattern D (holds write-ownership)
# =============================================================================


def test_operator_late_orders_scoped_excludes_other_client(_bind, operator_user_client_a):
    """identify_late_orders had NO client filter at all — any authenticated
    user could see every client's late work orders. Seed a CLIENT-B late
    production entry and confirm operator-A's response excludes it."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="late_orders_admin", role="admin")
    product_b = TestDataFactory.create_product(db, client_id="CLIENT-B")
    shift_b = TestDataFactory.create_shift(db, client_id="CLIENT-B")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    old_date = date.today() - timedelta(days=10)
    TestDataFactory.create_production_entry(
        db,
        client_id="CLIENT-B",
        product_id=product_b.product_id,
        shift_id=shift_b.shift_id,
        entered_by=admin.user_id,
        production_date=old_date,
        work_order_id=wo_b.work_order_id,
    )
    db.commit()

    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/late-orders")
        assert r.status_code == 200
        work_order_ids = [item["work_order"] for item in r.json()]
        assert wo_b.work_order_id not in work_order_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_chronic_holds_scoped_excludes_other_client(_bind, operator_user_client_a):
    """The /api/kpi/chronic-holds handler always passed client_id=None to
    identify_chronic_holds — any authenticated user saw every client's
    chronic holds. Seed a CLIENT-B chronic hold and confirm it's excluded."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="chronic_admin", role="admin")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    old_hold_date = datetime.now(tz=timezone.utc) - timedelta(days=40)
    hold_b = TestDataFactory.create_hold_entry(
        db,
        work_order_id=wo_b.work_order_id,
        client_id="CLIENT-B",
        created_by=admin.user_id,
        hold_status=HoldStatus.ON_HOLD,
        hold_date=old_hold_date,
    )
    db.commit()

    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/chronic-holds")
        assert r.status_code == 200
        hold_ids = [item["hold_id"] for item in r.json()]
        assert hold_b.hold_entry_id not in hold_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_quality_score_blocked_for_other_client(_bind, operator_user_client_a):
    """/api/quality/kpi/quality-score is product-keyed with no tenant check
    at all — any authenticated user could pass any product_id. Confirm a
    CLIENT-B product is now rejected for an operator scoped to CLIENT-A."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    product_b = TestDataFactory.create_product(db, client_id="CLIENT-B")
    db.commit()

    c = _as(operator_user_client_a)
    try:
        r = c.get(
            "/api/quality/kpi/quality-score",
            params={"product_id": product_b.product_id, "start_date": "2026-06-01", "end_date": "2026-06-30"},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_quality_score_allowed_for_own_client(_bind, operator_user_client_a):
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-A")
    product_a = TestDataFactory.create_product(db, client_id="CLIENT-A")
    db.commit()

    c = _as(operator_user_client_a)
    try:
        r = c.get(
            "/api/quality/kpi/quality-score",
            params={"product_id": product_a.product_id, "start_date": "2026-06-01", "end_date": "2026-06-30"},
        )
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_quality_score_404_for_missing_product(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get(
            "/api/quality/kpi/quality-score",
            params={"product_id": 999999, "start_date": "2026-06-01", "end_date": "2026-06-30"},
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_fpy_rty_breakdown_scoped_to_own_client(_bind, operator_user_client_a):
    """calculate_fpy_with_repair_breakdown/calculate_rty_with_repair_impact
    ignored client scope entirely, even though the handler already resolved
    a ClientScope. Seed quality entries for CLIENT-A and CLIENT-B in the
    same window and confirm operator-A's totals reflect CLIENT-A only."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-A")
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="fpy_admin", role="admin")
    wo_a = TestDataFactory.create_work_order(db, client_id="CLIENT-A")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    day = date(2026, 6, 15)
    TestDataFactory.create_quality_entry(
        db,
        work_order_id=wo_a.work_order_id,
        client_id="CLIENT-A",
        inspector_id=admin.user_id,
        inspection_date=day,
        units_inspected=100,
        units_defective=0,
    )
    TestDataFactory.create_quality_entry(
        db,
        work_order_id=wo_b.work_order_id,
        client_id="CLIENT-B",
        inspector_id=admin.user_id,
        inspection_date=day,
        units_inspected=1000,
        units_defective=0,
    )
    db.commit()

    c = _as(operator_user_client_a)
    try:
        r = c.get(
            "/api/quality/kpi/fpy-rty-breakdown",
            params={"start_date": "2026-06-14", "end_date": "2026-06-16"},
        )
        assert r.status_code == 200
        assert r.json()["fpy_breakdown"]["total_inspected"] == 100
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_supervisor_cannot_approve_hold_of_other_client(_bind):
    """approve_hold's inline ownership check is replaced with the shared
    verify_client_access helper. A CLIENT-A-scoped supervisor must still be
    denied on a CLIENT-B hold."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="hold_admin_d1", role="admin")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    hold_b = TestDataFactory.create_hold_entry(
        db,
        work_order_id=wo_b.work_order_id,
        client_id="CLIENT-B",
        created_by=admin.user_id,
        hold_status=HoldStatus.PENDING_HOLD_APPROVAL,
    )
    db.commit()

    supervisor_a = User(
        user_id="SUP-A-D1",
        username="supervisor_a_d1",
        email="supervisor_a_d1@test.com",
        role=UserRole.SUPERVISOR,
        client_id_assigned="CLIENT-A",
        is_active=True,
    )
    c = _as(supervisor_a)
    try:
        r = c.post(f"/api/holds/{hold_b.hold_entry_id}/approve-hold")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_request_resume_of_other_clients_hold(_bind, operator_user_client_a):
    """request_resume accepts any contributor-tier role (including operator),
    so an operator scoped to CLIENT-A exercises the ownership check directly."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="hold_admin_d2", role="admin")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    hold_b = TestDataFactory.create_hold_entry(
        db,
        work_order_id=wo_b.work_order_id,
        client_id="CLIENT-B",
        created_by=admin.user_id,
        hold_status=HoldStatus.ON_HOLD,
    )
    db.commit()

    c = _as(operator_user_client_a)
    try:
        r = c.post(f"/api/holds/{hold_b.hold_entry_id}/request-resume")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_supervisor_cannot_approve_resume_of_other_clients_hold(_bind):
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="hold_admin_d3", role="admin")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    hold_b = TestDataFactory.create_hold_entry(
        db,
        work_order_id=wo_b.work_order_id,
        client_id="CLIENT-B",
        created_by=admin.user_id,
        hold_status=HoldStatus.PENDING_RESUME_APPROVAL,
    )
    db.commit()

    supervisor_a = User(
        user_id="SUP-A-D3",
        username="supervisor_a_d3",
        email="supervisor_a_d3@test.com",
        role=UserRole.SUPERVISOR,
        client_id_assigned="CLIENT-A",
        is_active=True,
    )
    c = _as(supervisor_a)
    try:
        r = c.post(f"/api/holds/{hold_b.hold_entry_id}/approve-resume")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_leader_multi_client_can_approve_hold_across_assigned_clients(_bind, leader_user_multi_client):
    """Regression for the pre-fix bug: the inline ownership check compared
    db_hold.client_id against the RAW comma-separated client_id_assigned
    string, which incorrectly denied a multi-client leader's legitimate
    access to their second assigned client. verify_client_access correctly
    parses the assignment list, so this now succeeds."""
    db = _bind
    TestDataFactory.create_client(db, client_id="CLIENT-B")
    admin = TestDataFactory.create_user(db, username="hold_admin_d4", role="admin")
    wo_b = TestDataFactory.create_work_order(db, client_id="CLIENT-B")
    hold_b = TestDataFactory.create_hold_entry(
        db,
        work_order_id=wo_b.work_order_id,
        client_id="CLIENT-B",
        created_by=admin.user_id,
        hold_status=HoldStatus.PENDING_HOLD_APPROVAL,
    )
    db.commit()

    c = _as(leader_user_multi_client)
    try:
        r = c.post(f"/api/holds/{hold_b.hold_entry_id}/approve-hold")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
