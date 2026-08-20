from backend.seed.profiles import FULL, PROFILES, SMOKE
from backend.seed.scenarios import (
    CLIENT_TYPE_BY_PAY_MODEL,
    DEFECT_CODES,
    DEMO_PASSWORD,
    DOWNTIME_REASONS,
    ROOT_CAUSES,
    SCENARIOS,
    USERS,
    NarrativeWindow,
)


def test_full_profile_covers_twelve_months():
    assert FULL.days == 365


def test_smoke_profile_is_short_enough_for_tests():
    assert SMOKE.days == 14


def test_profiles_are_registered_by_name():
    assert PROFILES["full"] is FULL
    assert PROFILES["smoke"] is SMOKE


def test_four_clients_matching_the_spec():
    assert len(SCENARIOS) == 4
    assert tuple(s.client_id for s in SCENARIOS) == (
        "DEMO-PIECE",
        "DEMO-HOURLY",
        "DEMO-HYBRID",
        "SAMPLE_REF",
    )


def test_pay_models_are_distinct_where_the_spec_says_so():
    by_id = {s.client_id: s for s in SCENARIOS}
    assert by_id["DEMO-PIECE"].pay_model == "piece"
    assert by_id["DEMO-HOURLY"].pay_model == "hourly"
    assert by_id["DEMO-HYBRID"].pay_model == "hybrid"
    assert by_id["SAMPLE_REF"].pay_model == "hourly"


def test_sample_ref_is_the_healthy_control():
    """Without a client whose metrics stay in specification, every dashboard
    reads red and thresholds look broken rather than informative."""
    by_id = {s.client_id: s for s in SCENARIOS}
    assert by_id["SAMPLE_REF"].narrative == ()


def test_each_troubled_client_has_exactly_one_narrative_window():
    for scenario in SCENARIOS:
        if scenario.client_id == "SAMPLE_REF":
            continue
        assert len(scenario.narrative) == 1


def test_narrative_windows_are_ordered_and_in_the_past():
    for scenario in SCENARIOS:
        for w in scenario.narrative:
            assert w.start_month < 0
            assert w.start_month < w.end_month


def test_each_clients_narrative_window_matches_its_declared_episode():
    """Pins the exact (kind, start_month, end_month) triple per client, not
    just pooled invariants. Task 4's injection keys on `kind` per client, so
    swapping episodes between clients (or shifting their months) must fail
    here even though the generic ordering checks above would stay green."""
    by_id = {s.client_id: s for s in SCENARIOS}
    assert by_id["DEMO-PIECE"].narrative == (
        NarrativeWindow(kind="supplier_quality_crisis", start_month=-8, end_month=-6),
    )
    assert by_id["DEMO-HOURLY"].narrative == (
        NarrativeWindow(kind="equipment_reliability_decline", start_month=-5, end_month=-3),
    )
    assert by_id["DEMO-HYBRID"].narrative == (NarrativeWindow(kind="labor_disruption", start_month=-4, end_month=-2),)


def test_scenarios_are_immutable():
    import dataclasses

    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        SCENARIOS[0].client_id = "X"


def test_client_type_uses_the_live_vocabulary():
    """Read off the VM. A synonym here is how the current dataset ended up with
    a defect taxonomy nothing joins to."""
    assert set(CLIENT_TYPE_BY_PAY_MODEL.values()) == {"Piece Rate", "Hourly Rate", "Hybrid"}


def test_every_scenario_resolves_to_a_client_type():
    for s in SCENARIOS:
        assert s.client_type == CLIENT_TYPE_BY_PAY_MODEL[s.pay_model]


def test_defect_codes_are_catalog_codes_not_display_names():
    assert DEFECT_CODES == ("COLOR", "FABRIC", "MEASURE", "STAIN", "STITCH")


def test_downtime_and_root_cause_vocabularies_are_the_live_ones():
    assert DOWNTIME_REASONS == (
        "EQUIPMENT_FAILURE",
        "MAINTENANCE",
        "MATERIAL_SHORTAGE",
        "OPERATOR_UNAVAILABLE",
        "QUALITY_HOLD",
        "SETUP_CHANGEOVER",
    )
    assert ROOT_CAUSES == ("attendance", "machine", "materials", "other", "scheduling")


def test_all_six_roles_have_a_credential():
    """Spec section 9: the documented set covers all six roles, so the
    permission model is demonstrable rather than described."""
    assert {u.role for u in USERS} == {
        "admin",
        "poweruser",
        "leader",
        "supervisor",
        "operator",
        "viewer",
    }


def test_the_leader_reaches_several_clients_and_the_supervisor_one():
    leader = next(u for u in USERS if u.role == "leader")
    supervisor = next(u for u in USERS if u.role == "supervisor")

    assert len(leader.client_ids) == 3
    assert len(supervisor.client_ids) == 1


def test_platform_roles_are_scoped_to_no_client():
    for role in ("admin", "poweruser"):
        user = next(u for u in USERS if u.role == role)
        assert user.client_ids == ()


def test_every_user_client_id_is_a_real_scenario():
    known = {s.client_id for s in SCENARIOS}
    for u in USERS:
        for cid in u.client_ids:
            assert cid in known


def test_usernames_are_unique():
    names = [u.username for u in USERS]
    assert len(names) == len(set(names))


def test_password_is_a_single_documented_constant():
    """One constant, referenced by the runbook. Per-user passwords in a demo
    are a documentation burden with no security benefit."""
    assert DEMO_PASSWORD == "DemoSeed#2026"  # pragma: allowlist secret


def test_the_attribution_user_is_a_platform_scoped_seeded_user():
    """entered_by is a foreign key to USER, so the id has to resolve -- but
    resolving is not enough. Every client's production is attributed to this
    one user, so a user granted a single tenant puts that tenant's supervisor
    on all four clients' rows: not an FK error, but in a product whose
    client-scope authorization was just made uniform it reads as a
    tenant-isolation bug. The attribution user must belong to NO tenant."""
    from backend.seed.scenarios import ATTRIBUTION_USER_ID

    by_id = {u.user_id: u for u in USERS}
    assert ATTRIBUTION_USER_ID in by_id
    assert by_id[ATTRIBUTION_USER_ID].client_ids == ()


def test_the_unplanned_override_stays_inside_the_canonical_taxonomy():
    """The override exists so an equipment-reliability decline produces
    FAILURES rather than scheduled maintenance. Both halves are asserted
    against backend/orm/downtime_taxonomy.py, the single source of truth, so
    this cannot drift into a reason the application does not recognise or into
    a reason that is still planned."""
    from backend.orm.downtime_taxonomy import DEFAULT_CATEGORY_BY_REASON, PLANNED_DOWNTIME_REASONS
    from backend.seed.scenarios import REASON_BY_ROOT_CAUSE, UNPLANNED_REASON_BY_ROOT_CAUSE

    assert REASON_BY_ROOT_CAUSE["machine"] in PLANNED_DOWNTIME_REASONS
    assert UNPLANNED_REASON_BY_ROOT_CAUSE["machine"] not in PLANNED_DOWNTIME_REASONS
    # Same management category on both sides: the override changes whether the
    # stop was planned, never what it is attributed to.
    for cause, reason in UNPLANNED_REASON_BY_ROOT_CAUSE.items():
        assert DEFAULT_CATEGORY_BY_REASON[reason] == cause
    for cause, reason in REASON_BY_ROOT_CAUSE.items():
        assert DEFAULT_CATEGORY_BY_REASON[reason] == cause
    assert set(UNPLANNED_REASON_BY_ROOT_CAUSE) == set(REASON_BY_ROOT_CAUSE)


def test_every_scenario_declares_products():
    for s in SCENARIOS:
        assert len(s.products) == 3
