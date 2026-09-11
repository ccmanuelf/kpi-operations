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
from types import SimpleNamespace

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


class TestTheMergeIsPerField:
    """A client row supplies what it sets; the rest comes from the global row.

    Wholesale replacement made a target-only client row silently erase the global
    warning/critical bands -- so on the live demo the same measured 0.0% read
    "At Risk" for one metric and "Urgent" for another. The admin UI cannot set
    bands per-client at all (one numeric field per KPI), so inheritance is the
    ONLY mechanism by which a client's bands can exist; and the trap is not the
    seeder's, since `update_kpi_thresholds` creates client rows with bands of
    None too.
    """

    def test_a_target_only_client_row_inherits_the_global_bands(self, transactional_db):
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0, warning=75.0, critical=60.0)
        _threshold(db, client_id=client.client_id, kpi_key="efficiency", target=70.0)

        t = load_targets(db, client.client_id)["efficiency"]
        assert t.value == 70.0, "the client's own target must still win"
        assert (t.warning, t.critical) == (75.0, 60.0), "the global bands must be inherited"

    def test_a_client_band_still_wins_over_the_global_one(self, transactional_db):
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0, warning=75.0, critical=60.0)
        _threshold(db, client_id=client.client_id, kpi_key="efficiency", target=70.0, warning=40.0)

        t = load_targets(db, client.client_id)["efficiency"]
        assert t.warning == 40.0, "the client set this one"
        assert t.critical == 60.0, "and inherited this one"

    def test_a_zero_band_is_a_value_not_an_absence(self, transactional_db):
        # The merge keys on `is None`. Truthiness would treat a configured 0 as
        # unset and silently inherit over it -- the same defect PR-A fixed inside
        # check_threshold_breach.
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="ppm", target=500.0, warning=1000.0, critical=2000.0, higher="N")
        _threshold(db, client_id=client.client_id, kpi_key="ppm", target=100.0, warning=0.0, higher="N")

        t = load_targets(db, client.client_id)["ppm"]
        assert t.warning == 0.0, "a configured zero must not be overwritten by inheritance"
        assert t.critical == 2000.0

    def test_direction_is_inherited_when_the_client_row_has_none(self, transactional_db):
        """Defence in depth, and honestly scoped.

        `higher_is_better` is a NULLABLE column, and defaulting a NULL to "higher
        is better" would invert the verdict for every lower-is-better metric -- a
        PPM of 2000 against a target of 500 would read On Target. So the merge
        inherits it.

        A NULL is NOT reachable through the ORM: the column carries a Python-side
        `default="Y"` (orm/kpi_threshold.py), which the PUT route, the seeder and
        migration 0009 all go through. It is reachable by direct SQL, which is why
        this test writes one that way rather than pretending the ORM can.

        An earlier version of this test set the direction on BOTH rows, so it
        passed without exercising inheritance at all.
        """
        from sqlalchemy import text

        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="ppm", target=500.0, warning=1000.0, higher="N")
        _threshold(db, client_id=client.client_id, kpi_key="ppm", target=100.0, higher="N")
        db.execute(
            text("UPDATE KPI_THRESHOLD SET higher_is_better = NULL WHERE client_id = :c AND kpi_key = 'ppm'"),
            {"c": client.client_id},
        )
        db.expire_all()

        t = load_targets(db, client.client_id)["ppm"]
        assert t.higher_is_better is False, "a NULL direction must inherit, not default to Y"
        assert status_for(2000.0, t) != "On Target", "the verdict would have inverted"
        assert status_for(50.0, t) == "On Target"

    def test_inheritance_carries_a_global_Y_as_well_as_a_global_N(self, transactional_db):
        """Both directions, because one of them cannot discriminate.

        With a global "N", a broken inheritance that yields False agrees with the
        correct answer by accident -- which is exactly how the first mutation of
        this gate passed. A global "Y" separates them.
        """
        from sqlalchemy import text

        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="made_up_y", target=80.0, warning=70.0, higher="Y")
        _threshold(db, client_id=client.client_id, kpi_key="made_up_y", target=75.0, higher="Y")
        db.execute(
            text("UPDATE KPI_THRESHOLD SET higher_is_better = NULL WHERE client_id = :c AND kpi_key = 'made_up_y'"),
            {"c": client.client_id},
        )
        db.expire_all()

        t = load_targets(db, client.client_id)["made_up_y"]
        assert t.higher_is_better is True, "a global Y must be inherited as True"
        assert status_for(90.0, t) == "On Target"

    def test_a_client_row_may_still_override_the_direction(self, transactional_db):
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="made_up", target=50.0, higher="N")
        _threshold(db, client_id=client.client_id, kpi_key="made_up", target=50.0, higher="Y")

        assert load_targets(db, client.client_id)["made_up"].higher_is_better is True

    def test_a_direction_missing_everywhere_falls_back_to_higher_is_better(self, transactional_db):
        # Matching the column's own server default, decided once in `_resolve`
        # rather than silently inside every row read.
        db = transactional_db
        _threshold(db, client_id=None, kpi_key="made_up", target=50.0, higher=None)

        assert load_targets(db, None)["made_up"].higher_is_better is True

    def test_two_global_rows_do_not_splice_into_a_threshold_nobody_configured(self, transactional_db):
        """Merging is for the global-to-client boundary only.

        Two GLOBAL rows for one key are schema-permitted. Merging them into each
        other would take the target from one and the bands from the other,
        producing a combination nobody ever configured. Within a scope the highest
        threshold_id simply wins, whole.
        """
        db = transactional_db
        db.query(KPIThreshold).filter(KPIThreshold.client_id.is_(None), KPIThreshold.kpi_key == "oee").delete()
        for threshold_id, target, warning in (("AAA", 10.0, 5.0), ("ZZZ", 20.0, None)):
            db.add(
                KPIThreshold(
                    threshold_id=threshold_id,
                    client_id=None,
                    kpi_key="oee",
                    target_value=target,
                    warning_threshold=warning,
                    unit="%",
                    higher_is_better="Y",
                )
            )
        db.flush()

        t = load_targets(db, None)["oee"]
        assert (t.value, t.warning) == (20.0, None), "ZZZ must win WHOLE, not lend its target to AAA's band"

    def test_a_metric_with_no_global_row_still_resolves(self, transactional_db):
        # Merging must not require a global row to merge against.
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=client.client_id, kpi_key="made_up", target=12.0, warning=8.0)

        t = load_targets(db, client.client_id)["made_up"]
        assert (t.value, t.warning, t.critical) == (12.0, 8.0, None)

    def test_the_inheritance_changes_the_rendered_verdict(self, transactional_db):
        # The whole point, end to end: a target-only client row used to collapse
        # to the two-state scale. With the global bands inherited it escalates.
        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0, warning=75.0, critical=60.0)
        _threshold(db, client_id=client.client_id, kpi_key="efficiency", target=85.0)

        t = load_targets(db, client.client_id)["efficiency"]
        assert status_for(70.0, t) == "Warning", "70 breaches the inherited warning band of 75"
        assert status_for(55.0, t) == "Critical"

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

    def test_two_global_rows_for_one_metric_resolve_deterministically(self, transactional_db):
        """Both dialects exclude NULLs from a UNIQUE index.

        So `UNIQUE(client_id, kpi_key)` does NOT prevent two GLOBAL rows sharing a
        kpi_key, and without a total order which one a report reads would depend on
        the query plan. Nothing creates a duplicate today -- the PUT route updates
        in place and migration 0009 inserts only if absent -- but the schema
        permits it, and a nondeterministic target is worse than a wrong one.

        Resolving a structural guarantee for this is its own piece of work (it
        needs the nullable-discriminator trick migration 0008 used for coverage);
        this pins the read side so the report is at least stable.
        """
        db = transactional_db
        _delete_global = (
            db.query(KPIThreshold).filter(KPIThreshold.client_id.is_(None), KPIThreshold.kpi_key == "oee").delete()
        )
        assert _delete_global >= 0
        # Inserted LATER-id FIRST, so insertion order and id order disagree. A
        # stable sort with no tiebreak would keep insertion order and let the
        # second row win; the tiebreak makes the id decide instead.
        for threshold_id, target in (("ZZZ-LATER", 22.0), ("AAA-EARLIER", 11.0)):
            db.add(
                KPIThreshold(
                    threshold_id=threshold_id,
                    client_id=None,
                    kpi_key="oee",
                    target_value=target,
                    unit="%",
                    higher_is_better="Y",
                )
            )
        db.flush()

        # The highest threshold_id wins, every time, because the sort is total.
        assert load_targets(db, None)["oee"].value == 22.0
        assert load_targets(db, None)["oee"].value == 22.0

    def test_the_bands_and_direction_are_carried_through(self, transactional_db):
        db = transactional_db
        _threshold(
            db, client_id=None, kpi_key="ppm", target=500.0, warning=1000.0, critical=2000.0, unit="ppm", higher="N"
        )

        t = load_targets(db, None)["ppm"]
        assert (t.value, t.warning, t.critical, t.higher_is_better) == (500.0, 1000.0, 2000.0, False)


class TestStatusWhenNothingIsConfigured:
    def test_no_target_means_no_verdict(self):
        # Rendering "At Risk" against a target nobody set is the bug being
        # fixed; the honest answer is that no judgement was made.
        assert status_for(42.0, None) == "No Target"


class TestStatusWithATargetAndNoBands:
    """What the seeder writes, and therefore what a fresh deployment has."""

    EFF = Target(value=85.0, warning=None, critical=None, higher_is_better=True)

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
        ppm = Target(value=500.0, warning=None, critical=None, higher_is_better=False)
        assert status_for(500.0, ppm) == "On Target"
        assert status_for(499.0, ppm) == "On Target"
        assert status_for(501.0, ppm) == "At Risk"


class TestStatusWithBands:
    """What the VM's global rows carry, and what the admin screen can write."""

    EFF = Target(value=85.0, warning=75.0, critical=60.0, higher_is_better=True)

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
        ppm = Target(value=500.0, warning=1000.0, critical=2000.0, higher_is_better=False)
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

        t = Target(value=85.0, warning=75.0, critical=60.0, higher_is_better=True)
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


class TestAZeroThresholdIsAConfiguration:
    """`if critical_threshold` discarded a configured zero.

    Unreachable while every caller passed a literal; reachable now that these come
    from `KPI_THRESHOLD`, where an administrator can type 0.

    Every case below is LOWER-is-better, because that is where a zero band can
    actually be consulted. For a higher-is-better metric with a positive target, a
    value at or below a zero band is always below half of target, so the urgent
    ratio answers first and the band is never reached -- which is why an earlier
    draft of these tests passed with the bug still in place.
    """

    def test_a_zero_warning_band_is_honoured(self):
        # Defect rate: target 10, but warn the moment there are any at all.
        t = Target(value=10.0, warning=0.0, critical=None, higher_is_better=False)

        assert status_for(5.0, t) == "On Target"  # meets target
        assert status_for(15.0, t) == "Warning"  # 15 >= 0; discarded, this was "At Risk"

    def test_a_zero_critical_band_is_honoured(self):
        t = Target(value=10.0, warning=None, critical=0.0, higher_is_better=False)

        assert status_for(15.0, t) == "Critical"  # 15 >= 0; discarded, this was "At Risk"

    def test_a_zero_band_does_not_swallow_the_on_target_case(self):
        # The fix must not turn "meets target" into a breach.
        t = Target(value=10.0, warning=0.0, critical=0.0, higher_is_better=False)

        assert status_for(10.0, t) == "On Target"
        assert status_for(0.0, t) == "On Target"

    def test_the_underlying_breach_function_honours_zero(self):
        from backend.calculations.alerts import check_threshold_breach

        # Directly, on the one shape where a zero band is reachable.
        assert (
            check_threshold_breach(Decimal("15"), Decimal("10"), Decimal("0"), None, False) == "warning"
        ), "a zero warning band was discarded"
        assert (
            check_threshold_breach(Decimal("15"), Decimal("10"), None, Decimal("0"), False) == "critical"
        ), "a zero critical band was discarded"


class TestTheApiAndTheReportAgree:
    """`GET /api/kpi-thresholds` and `load_targets` must resolve identically.

    If they diverge, the admin screen and the PDF describe different thresholds
    for the same client -- the PDF-vs-Excel class #300 fixed, rebuilt between two
    layers instead of two formats.
    """

    def test_the_route_inherits_the_global_bands_too(self, transactional_db):
        from backend.routes.kpi.thresholds import get_kpi_thresholds

        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="efficiency", target=85.0, warning=75.0, critical=60.0)
        _threshold(db, client_id=client.client_id, kpi_key="efficiency", target=70.0)
        db.commit()

        scope = SimpleNamespace(client_ids=(client.client_id,))
        row = get_kpi_thresholds(client_id=client.client_id, db=db, current_user=None, scope=scope)["thresholds"][
            "efficiency"
        ]

        assert row["target_value"] == 70.0
        assert (row["warning_threshold"], row["critical_threshold"]) == (75.0, 60.0)
        assert row["is_global"] is False, "is_global still means 'a client row exists for this key'"

    def test_both_readers_agree_field_for_field(self, transactional_db):
        from backend.routes.kpi.thresholds import get_kpi_thresholds

        db = transactional_db
        client = TestDataFactory.create_client(db)
        # The client row carries NO direction, so both readers must INHERIT it.
        # Setting it on both rows (as an earlier version did) made this pass
        # without comparing the thing most likely to diverge. Written by direct
        # SQL because the ORM column default would supply "Y".
        from sqlalchemy import text

        _threshold(db, client_id=None, kpi_key="ppm", target=500.0, warning=1000.0, critical=2000.0, higher="N")
        _threshold(db, client_id=client.client_id, kpi_key="ppm", target=100.0, warning=0.0, higher="N")
        db.execute(
            text("UPDATE KPI_THRESHOLD SET higher_is_better = NULL WHERE client_id = :c AND kpi_key = 'ppm'"),
            {"c": client.client_id},
        )
        db.commit()

        scope = SimpleNamespace(client_ids=(client.client_id,))
        api = get_kpi_thresholds(client_id=client.client_id, db=db, current_user=None, scope=scope)["thresholds"]["ppm"]
        resolved = load_targets(db, client.client_id)["ppm"]

        assert api["target_value"] == resolved.value
        assert api["warning_threshold"] == resolved.warning
        assert api["critical_threshold"] == resolved.critical
        assert api["higher_is_better"] == "N", "the route must inherit the direction"
        assert (api["higher_is_better"] == "Y") is resolved.higher_is_better

    def test_the_route_resolves_duplicate_globals_the_same_way(self, transactional_db):
        """Two global rows for one key are schema-permitted on both dialects.

        The route's global pass used no ORDER BY, so which of them won depended on
        the query plan -- and could disagree with `load_targets`, which sorts by
        threshold_id. Same data, two answers, depending which surface you ask.
        """
        from backend.routes.kpi.thresholds import get_kpi_thresholds

        db = transactional_db
        client = TestDataFactory.create_client(db)
        db.query(KPIThreshold).filter(KPIThreshold.client_id.is_(None), KPIThreshold.kpi_key == "oee").delete()
        for threshold_id, target in (("ZZZ-WINS", 22.0), ("AAA-LOSES", 11.0)):
            db.add(
                KPIThreshold(
                    threshold_id=threshold_id,
                    client_id=None,
                    kpi_key="oee",
                    target_value=target,
                    unit="%",
                    higher_is_better="Y",
                )
            )
        db.commit()

        scope = SimpleNamespace(client_ids=(client.client_id,))
        api = get_kpi_thresholds(client_id=client.client_id, db=db, current_user=None, scope=scope)["thresholds"]["oee"]

        assert api["target_value"] == 22.0, "the highest threshold_id must win"
        assert api["target_value"] == load_targets(db, client.client_id)["oee"].value

    def test_a_client_band_of_zero_survives_the_route_too(self, transactional_db):
        from backend.routes.kpi.thresholds import get_kpi_thresholds

        db = transactional_db
        client = TestDataFactory.create_client(db)
        _threshold(db, client_id=None, kpi_key="ppm", target=500.0, warning=1000.0, higher="N")
        _threshold(db, client_id=client.client_id, kpi_key="ppm", target=100.0, warning=0.0, higher="N")
        db.commit()

        scope = SimpleNamespace(client_ids=(client.client_id,))
        api = get_kpi_thresholds(client_id=client.client_id, db=db, current_user=None, scope=scope)["thresholds"]["ppm"]

        assert api["warning_threshold"] == 0.0, "truthiness would have inherited 1000 over the configured 0"


class TestWhenAClientTargetSitsAtTheGlobalWarningLine:
    """Inherited bands are calibrated to the GLOBAL target, not the client's.

    The seeded `oee` case: client target 75, global bands 75 / 60. Every miss of
    the client's own target is then at least a Warning, and the At Risk tier is
    unreachable for that metric.

    Pinned as INTENDED rather than patched away. It is not incoherent -- the
    client's target sits exactly on the line the global configuration calls a
    warning, so "below target" genuinely is warning territory. Editing the seeded
    target to make a tier reappear would hide that reading behind nicer-looking
    demo data.

    The real remedy is a client able to set its own bands, which the threshold
    editor cannot do today (one numeric field per KPI) -- recorded in the spec,
    not worked around here.
    """

    BANDS_AT_TARGET = Target(value=75.0, warning=75.0, critical=60.0, higher_is_better=True)

    def test_meeting_the_client_target_is_still_on_target(self):
        assert status_for(75.0, self.BANDS_AT_TARGET) == "On Target"
        assert status_for(80.0, self.BANDS_AT_TARGET) == "On Target"

    def test_any_miss_is_at_least_a_warning(self):
        assert status_for(74.9, self.BANDS_AT_TARGET) == "Warning"
        assert status_for(70.0, self.BANDS_AT_TARGET) == "Warning"

    def test_the_lower_bands_still_work(self):
        assert status_for(60.0, self.BANDS_AT_TARGET) == "Critical"
        assert status_for(30.0, self.BANDS_AT_TARGET) == "Urgent"

    def test_the_at_risk_tier_is_genuinely_unreachable_here(self):
        # Documented explicitly so a future reader does not treat its absence as a
        # regression in the status scale.
        verdicts = {status_for(v, self.BANDS_AT_TARGET) for v in (74.99, 74.0, 70.0, 65.0, 60.1)}
        assert "At Risk" not in verdicts, verdicts
