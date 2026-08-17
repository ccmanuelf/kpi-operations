from backend.seed.profiles import FULL, PROFILES, SMOKE
from backend.seed.scenarios import SCENARIOS


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


def test_scenarios_are_immutable():
    import dataclasses

    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        SCENARIOS[0].client_id = "X"
