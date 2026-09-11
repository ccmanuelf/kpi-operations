"""Where a report's targets and its On Target / At Risk verdict come from.

Both generators used to carry inline literals -- efficiency 85, FPY 99, PPM
1000, absenteeism 5 -- and judged every client against them. `KPI_THRESHOLD`
has stored per-client and global targets all along, editable from the admin
settings screen, so the report was marking clients At Risk against numbers they
never set. Four of the five summary literals disagreed with what the product
itself stored.

The resolution is the same one `/api/kpi-thresholds` already implements: a
client's own row overrides the global (`client_id IS NULL`) row, per `kpi_key`.

The status scale deliberately composes two different questions, because
`check_threshold_breach` alone cannot answer the report's:

  * "is this meeting target?" -- a direction-aware comparison, which is what
    the summary column has always claimed to show.
  * "how bad is the miss?" -- `calculations/alerts.py::check_threshold_breach`,
    the product's own breach definition, reused rather than re-derived.

Composing them matters because a row with a target and no bands (which is what
the seeder writes, and therefore what a fresh deployment has) makes
`check_threshold_breach` return None for anything above half of target. Asked on
its own it would call an efficiency of 50% against a target of 85% "no breach".
"""

from decimal import Decimal

import pytest

from backend.db.factories import TestDataFactory
from backend.orm.kpi_threshold import KPIThreshold
from backend.reports.targets import Target, load_targets, status_for


def _threshold(db, *, client_id, kpi_key, target, warning=None, critical=None, unit="%", higher="Y"):
    row = KPIThreshold(
        threshold_id=f"THR-{client_id or 'GLOBAL'}-{kpi_key}",
        client_id=client_id,
        kpi_key=kpi_key,
        target_value=target,
        warning_threshold=warning,
        critical_threshold=critical,
        unit=unit,
        higher_is_better=higher,
    )
    db.add(row)
    db.flush()
    return row


class TestResolution:
    def test_the_global_row_is_used_when_the_client_has_none(self, transactional_db):
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0)

        assert load_targets(db, client.client_id)["efficiency"].value == 85.0

    def test_a_client_row_overrides_the_global_row(self, transactional_db):
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0)
        _threshold(db, client_id=client.client_id, kpi_key="efficiency", target=70.0)

        assert load_targets(db, client.client_id)["efficiency"].value == 70.0

    def test_another_client_s_row_is_not_visible(self, transactional_db):
        # The same tenancy rule the rest of the product follows: one client's
        # configuration must not reach another client's report.
        db = transactional_db
        mine = TestDataFactory.create_client(db)
        theirs = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0)
        _threshold(db, client_id=theirs.client_id, kpi_key="efficiency", target=50.0)

        assert load_targets(db, mine.client_id)["efficiency"].value == 85.0

    def test_an_all_clients_report_sees_only_global_rows(self, transactional_db):
        # client_id=None means "every client", which has no single client's
        # overrides to apply -- so it reads the global configuration.
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0)
        _threshold(db, client_id=client.client_id, kpi_key="efficiency", target=70.0)

        assert load_targets(db, None)["efficiency"].value == 85.0

    def test_an_unconfigured_metric_is_absent_rather_than_defaulted(self, transactional_db):
        # No invented fallback. The caller renders "no target configured",
        # which is the truth, instead of a literal nobody chose.
        #
        # `rty` deliberately: migration 0009 supplies a global default for every
        # metric the report renders today, so an unconfigured key has to be one
        # whose section does not exist yet. That is also why the generators are
        # tested against a DELETED global row rather than an absent one -- see
        # test_report_target_wiring.py::_delete_global.
        db = transactional_db
        client = TestDataFactory.create_client(db)

        assert load_targets(db, client.client_id).get("rty") is None

    def test_the_bands_and_direction_are_carried_through(self, transactional_db):
        db = transactional_db
        _threshold(
            db, client_id=None, kpi_key="ppm", target=500.0, warning=1000.0, critical=2000.0, unit="ppm", higher="N"
        )

        t = load_targets(db, None)["ppm"]
        assert (t.value, t.warning, t.critical, t.unit, t.higher_is_better) == (500.0, 1000.0, 2000.0, "ppm", False)


class TestStatusWhenNothingIsConfigured:
    def test_no_target_means_no_verdict(self):
        # Rendering "At Risk" against a target nobody set is the bug being
        # fixed; the honest answer is that no judgement was made.
        assert status_for(42.0, None) == "No Target"


class TestStatusWithATargetAndNoBands:
    """What the seeder writes, and therefore what a fresh deployment has."""

    EFF = Target(value=85.0, warning=None, critical=None, unit="%", higher_is_better=True)

    def test_meeting_target_is_on_target(self):
        assert status_for(85.0, self.EFF) == "On Target"
        assert status_for(90.0, self.EFF) == "On Target"

    def test_missing_target_is_at_risk(self):
        assert status_for(84.9, self.EFF) == "At Risk"

    def test_a_bad_miss_is_still_only_at_risk_without_bands(self):
        # check_threshold_breach WOULD call 40 "urgent" here (below half of
        # target) -- but with no warning/critical configured, escalating past
        # At Risk would be inventing a severity the admin never set. The one
        # ratio rule that fires without configuration is deliberately not
        # promoted into the report.
        assert status_for(40.0, self.EFF) == "At Risk"

    def test_direction_is_honoured_for_lower_is_better(self):
        ppm = Target(value=500.0, warning=None, critical=None, unit="ppm", higher_is_better=False)
        assert status_for(500.0, ppm) == "On Target"
        assert status_for(499.0, ppm) == "On Target"
        assert status_for(501.0, ppm) == "At Risk"


class TestStatusWithBands:
    """What the VM's global rows carry, and what the admin screen can write."""

    EFF = Target(value=85.0, warning=75.0, critical=60.0, unit="%", higher_is_better=True)

    def test_meeting_target_is_on_target(self):
        assert status_for(85.0, self.EFF) == "On Target"

    def test_below_target_but_above_the_warning_band_is_at_risk(self):
        # 80 misses the 85 target but breaches nothing -- the distinction the
        # old hardcoded `target * 0.95` heuristic was pretending to draw, now
        # drawn by the configured band instead.
        assert status_for(80.0, self.EFF) == "At Risk"

    def test_the_warning_band_reads_warning(self):
        assert status_for(75.0, self.EFF) == "Warning"
        assert status_for(61.0, self.EFF) == "Warning"

    def test_the_critical_band_reads_critical(self):
        assert status_for(60.0, self.EFF) == "Critical"
        assert status_for(43.0, self.EFF) == "Critical"

    def test_far_below_target_reads_urgent(self):
        # check_threshold_breach's own rule: below half of target.
        assert status_for(42.0, self.EFF) == "Urgent"

    def test_lower_is_better_bands_ascend(self):
        ppm = Target(value=500.0, warning=1000.0, critical=2000.0, unit="ppm", higher_is_better=False)
        assert status_for(400.0, ppm) == "On Target"
        assert status_for(900.0, ppm) == "At Risk"
        assert status_for(1000.0, ppm) == "Warning"
        assert status_for(2000.0, ppm) == "Critical"
        assert status_for(2501.0, ppm) == "Urgent"


class TestAgreementWithTheProductsOwnBreachRule:
    def test_every_escalated_status_matches_check_threshold_breach(self):
        # The report must not invent a second opinion about what counts as a
        # breach. For any value that misses target, the escalation above
        # "At Risk" is exactly what calculations/alerts.py says it is.
        from backend.calculations.alerts import check_threshold_breach

        t = Target(value=85.0, warning=75.0, critical=60.0, unit="%", higher_is_better=True)
        names = {"warning": "Warning", "critical": "Critical", "urgent": "Urgent", None: "At Risk"}

        for value in (84.9, 80.0, 75.0, 70.0, 60.0, 50.0, 42.0, 10.0):
            breach = check_threshold_breach(
                Decimal(str(value)), Decimal("85.0"), Decimal("75.0"), Decimal("60.0"), True
            )
            assert status_for(value, t) == names[breach], f"disagreed at {value}"


@pytest.mark.parametrize("higher", ["Y", "N"])
def test_higher_is_better_is_read_from_the_column_not_guessed(transactional_db, higher):
    # The generators hardcoded a `higher_better` literal per row. It is a
    # stored column, and a metric's direction is the admin's to declare.
    db = transactional_db
    _threshold(db, client_id=None, kpi_key="made_up_metric", target=50.0, higher=higher)

    assert load_targets(db, None)["made_up_metric"].higher_is_better is (higher == "Y")
