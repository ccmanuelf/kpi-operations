"""Tests for the frontend field-usage extractor.

See backend/tests/contract/frontend_usage.py for what this extractor does
and does not see.
"""


def test_extractor_finds_a_known_field_the_ui_reads():
    """kpi.ts maps by_reason off the absenteeism response. If the extractor
    cannot see a field this obvious, it will not protect the subtle ones."""
    from backend.tests.contract.frontend_usage import fields_read_by_frontend

    usage = fields_read_by_frontend()

    assert "by_reason" in usage["/api/attendance/kpi/absenteeism"]


def test_wrapper_hop_resolves_a_field_for_a_trend_endpoint():
    """kpi.ts defines `getEfficiencyTrend` as a thin wrapper around
    `api.get('/kpi/efficiency/trend', ...)` with no field reads of its own --
    the wrapper is called BY NAME from stores/kpi.ts instead
    (`() => api.getEfficiencyTrend(params)`), where the response is threaded
    through `_extractInferenceFromResponse`, which reads
    `response?.has_estimated`. Without the wrapper-name hop (pass 1: map
    wrapper name -> endpoint in services/api/*.ts; pass 2: attribute fields
    read anywhere a wrapper name is referenced elsewhere in frontend/src),
    this endpoint resolves to an empty field set -- exactly the /api/kpi/*
    /trend cluster Task 6 converts, and precisely the failure mode that would
    make a frontend cross-check step pass by finding nothing to check.

    NOTE: `has_estimated` is real production code but is not itself a
    trend-point field -- it is read off the *primary* efficiency response
    elsewhere in the same file as the wrapper reference, and is attributed
    to the trend endpoint because pass 2 matches at whole-file granularity
    (see frontend_usage.py's module docstring). This test guards the HOP
    MECHANISM (a wrapper's fields are no longer invisible just because they
    are read in a different file than the one that defines it) -- it does
    not claim the trend cluster's own `value` field is covered, which the
    module docstring records as a known, deliberately unresolved gap.
    """
    from backend.tests.contract.frontend_usage import fields_read_by_frontend

    usage = fields_read_by_frontend()

    assert "has_estimated" in usage["/api/kpi/efficiency/trend"]


def test_a_blind_endpoint_reports_no_coverage_rather_than_silence():
    """An empty result and an unseeable endpoint must not look alike.

    Measured 2026-08-25: all eight /api/kpi/*/trend endpoints return NON-EMPTY
    field sets that contain neither `date` nor `value` -- the only two fields
    they actually return. The listed names are bleed from unrelated code in the
    same file. So the coverage metric read 10/10 while real protection was 0/10.

    A cross-check printing "read-but-not-sent: []" is identical whether the
    extractor looked and found nothing wrong or could not see the endpoint at
    all. The second is not a pass, and this is what stops it being read as one.
    """
    from backend.tests.contract.frontend_usage import coverage_of, fields_read_by_frontend

    usage = fields_read_by_frontend()

    # the trap: non-empty, yet missing both real fields
    trend = usage.get("/api/kpi/efficiency/trend", set())
    assert "value" not in trend
    assert "date" not in trend

    assert coverage_of("/api/kpi/efficiency/trend") == "NO_COVERAGE"
    assert coverage_of("/api/attendance/kpi/absenteeism") == "COVERED"
