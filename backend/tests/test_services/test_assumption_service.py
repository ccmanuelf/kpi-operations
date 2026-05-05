"""
AssumptionService — Phase 2 dual-view architecture.

Real-DB tests via transactional_db + TestDataFactory (no mocks per project rule).
Covers the propose → approve → retire lifecycle, role gates, audit-log writes,
overlap auto-retirement, effective-set lookup, and history retrieval.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.orm.calculation_assumption import (
    AssumptionChange,
    AssumptionStatus,
    MetricAssumptionDependency,
)
from backend.services.assumption_service import AssumptionService
from backend.tests.fixtures.factories import TestDataFactory


def _make_users(db):
    """Create one client and three users (admin / poweruser / leader)."""

    client = TestDataFactory.create_client(db, client_id="CLIENT_DEMO")
    admin = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    poweruser = TestDataFactory.create_user(db, role="poweruser", client_id=client.client_id)
    leader = TestDataFactory.create_user(db, role="leader", client_id=client.client_id)
    db.commit()
    return client, admin, poweruser, leader


class TestPropose:
    def test_poweruser_can_propose(self, transactional_db):
        client, _admin, poweruser, _leader = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)

        record = svc.propose(
            client_id=client.client_id,
            assumption_name="ideal_cycle_time_source",
            value="engineering_standard",
            rationale="Use engineering-standard times for new lines.",
        )

        assert record.assumption_id is not None
        assert record.status == AssumptionStatus.PROPOSED
        assert record.proposed_by == poweruser.user_id
        assert json.loads(record.value_json) == "engineering_standard"

    def test_admin_can_propose(self, transactional_db):
        client, admin, _, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, admin)
        record = svc.propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )
        assert record.proposed_by == admin.user_id

    def test_leader_cannot_propose(self, transactional_db):
        client, _, _, leader = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, leader)
        with pytest.raises(Exception) as exc_info:
            svc.propose(
                client_id=client.client_id,
                assumption_name="setup_treatment",
                value="count_as_downtime",
            )
        assert exc_info.value.status_code == 403

    def test_unknown_assumption_name_rejected(self, transactional_db):
        client, _, poweruser, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)
        with pytest.raises(Exception) as exc_info:
            svc.propose(
                client_id=client.client_id,
                assumption_name="not_in_catalog",
                value="anything",
            )
        assert exc_info.value.status_code == 400

    def test_invalid_value_rejected(self, transactional_db):
        client, _, poweruser, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)
        with pytest.raises(Exception) as exc_info:
            svc.propose(
                client_id=client.client_id,
                assumption_name="ideal_cycle_time_source",
                value="bogus_choice",
            )
        assert exc_info.value.status_code == 400

    def test_otd_buffer_pct_range_enforced(self, transactional_db):
        client, _, poweruser, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)
        with pytest.raises(Exception) as exc_info:
            svc.propose(
                client_id=client.client_id,
                assumption_name="otd_carrier_buffer_pct",
                value=150,
            )
        assert exc_info.value.status_code == 400

        # Valid numeric works
        record = svc.propose(
            client_id=client.client_id,
            assumption_name="otd_carrier_buffer_pct",
            value=10,
        )
        assert json.loads(record.value_json) == 10

    def test_propose_writes_change_log(self, transactional_db):
        client, _, poweruser, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)
        record = svc.propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )

        changes = (
            transactional_db.query(AssumptionChange)
            .filter(AssumptionChange.assumption_id == record.assumption_id)
            .all()
        )
        assert len(changes) == 1
        assert changes[0].new_status == AssumptionStatus.PROPOSED.value
        assert changes[0].changed_by == poweruser.user_id

    def test_invalid_window_rejected(self, transactional_db):
        client, _, poweruser, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)
        with pytest.raises(Exception) as exc_info:
            svc.propose(
                client_id=client.client_id,
                assumption_name="setup_treatment",
                value="count_as_downtime",
                effective_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
                expiration_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        assert exc_info.value.status_code == 400


class TestApprove:
    def test_admin_approves_proposed(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="yield_baseline_source",
            value="theoretical",
        )

        approved = AssumptionService(transactional_db, admin).approve(record.assumption_id)

        assert approved.status == AssumptionStatus.ACTIVE
        assert approved.approved_by == admin.user_id
        assert approved.approved_at is not None

    def test_poweruser_cannot_approve(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="yield_baseline_source",
            value="theoretical",
        )
        with pytest.raises(Exception) as exc_info:
            AssumptionService(transactional_db, poweruser).approve(record.assumption_id)
        assert exc_info.value.status_code == 403

    def test_cannot_approve_active(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="yield_baseline_source",
            value="theoretical",
        )
        AssumptionService(transactional_db, admin).approve(record.assumption_id)
        with pytest.raises(Exception) as exc_info:
            AssumptionService(transactional_db, admin).approve(record.assumption_id)
        assert exc_info.value.status_code == 409

    def test_approve_auto_retires_overlapping_active(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        first = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )
        AssumptionService(transactional_db, admin).approve(first.assumption_id)

        second = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="exclude_from_availability",
        )
        AssumptionService(transactional_db, admin).approve(second.assumption_id)

        transactional_db.refresh(first)
        assert first.status == AssumptionStatus.RETIRED
        assert first.retired_by == admin.user_id


class TestRetire:
    def test_admin_retires_active(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="otd_carrier_buffer_pct",
            value=5,
        )
        AssumptionService(transactional_db, admin).approve(record.assumption_id)

        retired = AssumptionService(transactional_db, admin).retire(
            record.assumption_id, change_reason="vendor changed"
        )

        assert retired.status == AssumptionStatus.RETIRED
        assert retired.retired_by == admin.user_id

    def test_cannot_retire_proposed(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="otd_carrier_buffer_pct",
            value=5,
        )
        with pytest.raises(Exception) as exc_info:
            AssumptionService(transactional_db, admin).retire(record.assumption_id)
        assert exc_info.value.status_code == 409


class TestUpdateProposal:
    def test_proposer_can_edit_own(self, transactional_db):
        client, _, poweruser, _ = _make_users(transactional_db)
        svc = AssumptionService(transactional_db, poweruser)
        record = svc.propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )
        updated = svc.update_proposal(
            record.assumption_id,
            value="exclude_from_availability",
            rationale="reconsidered",
            change_reason="changed_mind",
        )
        assert json.loads(updated.value_json) == "exclude_from_availability"
        assert updated.rationale == "reconsidered"

    def test_admin_can_edit_others_proposal(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )
        updated = AssumptionService(transactional_db, admin).update_proposal(
            record.assumption_id, rationale="admin clarified"
        )
        assert updated.rationale == "admin clarified"

    def test_cannot_edit_active(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )
        AssumptionService(transactional_db, admin).approve(record.assumption_id)
        with pytest.raises(Exception) as exc_info:
            AssumptionService(transactional_db, admin).update_proposal(record.assumption_id, rationale="too late")
        assert exc_info.value.status_code == 409


class TestEffectiveSet:
    def test_returns_only_active_in_window(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        # An ACTIVE entry whose window straddles "now"
        active = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="ideal_cycle_time_source",
            value="engineering_standard",
            effective_date=datetime.now(tz=timezone.utc) - timedelta(days=30),
            expiration_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
        )
        AssumptionService(transactional_db, admin).approve(active.assumption_id)

        # A PROPOSED entry that should be excluded
        AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="yield_baseline_source",
            value="theoretical",
        )

        effective = AssumptionService(transactional_db, admin).get_effective_set(client_id=client.client_id)
        assert "ideal_cycle_time_source" in effective
        assert "yield_baseline_source" not in effective

    def test_excludes_records_outside_window(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        record = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
            effective_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        AssumptionService(transactional_db, admin).approve(record.assumption_id)

        # Asking for "today" should exclude a future-effective record.
        effective = AssumptionService(transactional_db, admin).get_effective_set(
            client_id=client.client_id,
            as_of=datetime.now(tz=timezone.utc),
        )
        assert "setup_treatment" not in effective


class TestHistory:
    def test_history_returns_changes_in_descending_order(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        svc_p = AssumptionService(transactional_db, poweruser)
        svc_a = AssumptionService(transactional_db, admin)
        record = svc_p.propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",
        )
        svc_p.update_proposal(record.assumption_id, rationale="added rationale")
        svc_a.approve(record.assumption_id)

        history = svc_a.get_history(record.assumption_id)
        assert len(history) == 3
        # Approve change is the most recent
        assert history[0].new_status == AssumptionStatus.ACTIVE.value


class TestCatalog:
    def test_catalog_lists_all_v1_assumptions(self):
        catalog = AssumptionService.get_catalog()
        for name in (
            "planned_production_time_basis",
            "ideal_cycle_time_source",
            "setup_treatment",
            "scrap_classification_rule",
            "otd_carrier_buffer_pct",
            "yield_baseline_source",
        ):
            assert name in catalog
            assert "description" in catalog[name]


class TestVarianceReport:
    def test_no_active_assumptions_yields_empty_list(self, transactional_db):
        client, admin, _, _ = _make_users(transactional_db)
        rows = AssumptionService(transactional_db, admin).get_variance_report()
        assert rows == []

    def test_active_categorical_at_default_has_zero_magnitude(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        # Approve a catalog-default categorical value
        rec = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="count_as_downtime",  # this IS the default
        )
        AssumptionService(transactional_db, admin).approve(rec.assumption_id)

        rows = AssumptionService(transactional_db, admin).get_variance_report()
        assert len(rows) == 1
        assert rows[0]["assumption_name"] == "setup_treatment"
        assert rows[0]["deviates_from_default"] is False
        assert rows[0]["deviation_magnitude"] == 0.0

    def test_active_categorical_off_default_has_unit_magnitude(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        rec = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="exclude_from_availability",
        )
        AssumptionService(transactional_db, admin).approve(rec.assumption_id)

        rows = AssumptionService(transactional_db, admin).get_variance_report()
        assert rows[0]["deviates_from_default"] is True
        assert rows[0]["deviation_magnitude"] == 1.0

    def test_otd_buffer_magnitude_is_numeric(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        rec = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="otd_carrier_buffer_pct",
            value=12,
        )
        AssumptionService(transactional_db, admin).approve(rec.assumption_id)

        rows = AssumptionService(transactional_db, admin).get_variance_report()
        # Buffer of 12% → deviation magnitude is 12.0
        assert rows[0]["deviation_magnitude"] == 12.0
        assert rows[0]["deviates_from_default"] is True

    def test_stale_flag_triggers_after_threshold(self, transactional_db):
        from datetime import timedelta

        client, admin, poweruser, _ = _make_users(transactional_db)
        rec = AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="setup_treatment",
            value="exclude_from_availability",
        )
        AssumptionService(transactional_db, admin).approve(rec.assumption_id)
        # Backdate the approval so it qualifies as stale
        rec.approved_at = datetime.now(tz=timezone.utc) - timedelta(days=400)
        transactional_db.commit()

        rows = AssumptionService(transactional_db, admin).get_variance_report(stale_after_days=365)
        assert rows[0]["is_stale"] is True
        assert rows[0]["days_since_review"] >= 400

    def test_tenant_isolation_for_non_admin(self, transactional_db):
        client_a = TestDataFactory.create_client(transactional_db, client_id="VARIANCE-CLIENT-A")
        client_b = TestDataFactory.create_client(transactional_db, client_id="VARIANCE-CLIENT-B")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id=None)
        poweruser = TestDataFactory.create_user(transactional_db, role="poweruser", client_id=None)
        leader_a = TestDataFactory.create_user(transactional_db, role="leader", client_id=client_a.client_id)
        transactional_db.commit()

        # One assumption per client
        for cid in (client_a.client_id, client_b.client_id):
            rec = AssumptionService(transactional_db, poweruser).propose(
                client_id=cid,
                assumption_name="setup_treatment",
                value="exclude_from_availability",
            )
            AssumptionService(transactional_db, admin).approve(rec.assumption_id)

        # Admin sees both
        admin_rows = AssumptionService(transactional_db, admin).get_variance_report()
        assert {r["client_id"] for r in admin_rows} == {client_a.client_id, client_b.client_id}

        # Leader sees only their assigned client
        leader_rows = AssumptionService(transactional_db, leader_a).get_variance_report()
        assert {r["client_id"] for r in leader_rows} == {client_a.client_id}

    def test_inactive_assumptions_excluded(self, transactional_db):
        client, admin, poweruser, _ = _make_users(transactional_db)
        # PROPOSED record (not yet active) should NOT appear in variance
        AssumptionService(transactional_db, poweruser).propose(
            client_id=client.client_id,
            assumption_name="yield_baseline_source",
            value="theoretical",
        )
        rows = AssumptionService(transactional_db, admin).get_variance_report()
        assert rows == []


class TestDependenciesQuery:
    def test_list_dependencies_filterable(self, transactional_db):
        client, admin, _, _ = _make_users(transactional_db)
        # Seed a couple of dependency rows
        transactional_db.add(MetricAssumptionDependency(metric_name="oee", assumption_name="setup_treatment"))
        transactional_db.add(MetricAssumptionDependency(metric_name="otd", assumption_name="otd_carrier_buffer_pct"))
        transactional_db.commit()

        svc = AssumptionService(transactional_db, admin)
        all_deps = svc.list_dependencies()
        assert len(all_deps) >= 2

        oee_only = svc.list_dependencies(metric_name="oee")
        assert all(d.metric_name == "oee" for d in oee_only)
