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


def test_bleed_does_not_count_as_coverage():
    """Task 8's exact measured case. `GET /api/kpi/efficiency/by-product`'s
    real fields (from the golden master) are `actual_output`, `efficiency`,
    `product_id`, `product_name`. The extractor finds `avg_efficiency` for
    this endpoint -- bled in from the unrelated `/api/kpi/dashboard` wrapper
    in the same kpi.ts file, which really does have an `avg_efficiency`
    field. Zero intersection with this route's own fields, so this must
    report NO_FIELDS_FOUND, not COVERED. Before Task 8's fix this asserted
    (and got) COVERED -- the bug this whole task exists to repair.
    """
    from backend.tests.contract.frontend_usage import coverage_of, fields_read_by_frontend

    usage = fields_read_by_frontend()

    # the trap: non-empty, and even plausible-looking, yet none of it is
    # this route's own field.
    assert "avg_efficiency" in usage["/api/kpi/efficiency/by-product"]
    assert "efficiency" not in usage["/api/kpi/efficiency/by-product"]

    assert coverage_of("/api/kpi/efficiency/by-product") == "NO_FIELDS_FOUND"


def test_genuine_field_overlap_still_reports_covered():
    """Guards against over-correcting the other way. `GET /api/kpi/dashboard`
    is the one honest COVERED the Task 7 pilot measured: the extractor finds
    `avg_efficiency` and `avg_performance`, and both are real top-level
    fields of this route's own golden master shape (`[].avg_efficiency`,
    `[].avg_performance`, alongside `date`, `entry_count`, `total_units`).
    If the intersection rule were tightened until nothing reports COVERED,
    this is the case that would catch it.
    """
    from backend.tests.contract.frontend_usage import coverage_of

    assert coverage_of("/api/kpi/dashboard") == "COVERED"


def test_missing_golden_truth_cannot_report_covered():
    """`GET /api/kpi/otd/by-client`'s golden master entry is `[]` -- reached,
    but no fields were ever recorded (no matching seed data at capture
    time) -- so this route's real field names are unknown, not empty-by-fact.
    The extractor still finds a non-empty (bleed) field set for it. Without
    a real target to intersect against, COVERED can never be trustworthy
    here, so this must report NO_FIELDS_FOUND -- the same as the `<status:
    ...>` case the brief calls out, reached by a different golden-master
    shape (an empty list rather than a status placeholder).
    """
    from backend.tests.contract.frontend_usage import coverage_of, fields_read_by_frontend

    usage = fields_read_by_frontend()

    # the trap: found is NOT empty, so a naive "found or not" check would
    # short-circuit straight to COVERED.
    assert usage.get("/api/kpi/otd/by-client")

    assert coverage_of("/api/kpi/otd/by-client") == "NO_FIELDS_FOUND"


def test_real_field_names_uses_top_level_segments_only():
    """`GET /api/kpi/dashboard/aggregated`'s golden master records nested
    dotted paths, e.g. `trends.efficiency[].date`. `_FIELD` can only ever
    capture a field name immediately after one of its receiver tokens
    (`d.`, `data.`, ...) -- never a chained `d.trends.efficiency.date` -- so
    the only name it could legitimately produce here is the TOP segment,
    `trends`. Real field names must be exactly that top segment, not every
    segment in the path: `date` is two levels deep and must NOT count as one
    of this route's real fields, or a `.date` bleed from anywhere in the
    file (an extremely common property name elsewhere in this codebase)
    would falsely intersect against a route the extractor never actually
    read.
    """
    from backend.tests.contract.frontend_usage import _real_field_names

    real = _real_field_names("/api/kpi/dashboard/aggregated")

    assert "trends" in real
    assert "date" not in real


def test_real_field_names_empty_for_status_placeholder_entry():
    """`GET /api/kpi/labor-hours`'s golden master entry is `["<status:422>"]`
    -- the capture harness never reached a real response body. That carries
    no field information at all, so the real field set must be empty, never
    `{"<status:422>"}` or any other artifact of the placeholder string
    itself leaking through as if it were a field name.
    """
    from backend.tests.contract.frontend_usage import _real_field_names

    assert _real_field_names("/api/kpi/labor-hours") == frozenset()


def test_real_field_names_empty_for_a_non_json_entry():
    """`GET /api/reports/comprehensive/excel`'s golden master entry is
    `["<non-json>"]` -- the route WAS reached, and answered with an .xlsx
    stream rather than JSON. That carries no field information either, but it
    does not start with `<status:`, so the original special case let the
    literal string `<non-json>` through as if it were a field named
    `<non-json>`.

    It never flipped a verdict, because no frontend read matches that string
    -- which is exactly why it survived unnoticed on 17 entries. Task 8b took
    it to 29 (nine DELETEs that answer 204 with an empty body, three QR image
    routes) and added a second placeholder flavour, so the rule is now
    "anything that starts with `<` is a placeholder" rather than a list of the
    ones seen so far.
    """
    from backend.tests.contract.frontend_usage import _real_field_names

    assert _real_field_names("/api/reports/comprehensive/excel") == frozenset()


def test_real_field_names_empty_for_a_blocked_entry():
    """`DELETE /api/part-opportunities/{part_number}`'s golden master entry is
    `["<blocked:part_number>"]`: no `part_number` can be resolved because
    `PART_OPPORTUNITIES` has zero seeded rows, so no request was ever issued.
    A `<blocked:...>` entry is the strongest possible statement that this
    route's real fields are UNKNOWN, so it must never contribute a field name
    -- least of all one that reads like the param that blocked it.

    Was `GET /api/jobs/{job_id}/yield` until S3 seeded JOB and that entry
    became a real eight-key shape. The example has to be a route that is STILL
    blocked, or this test passes for the wrong reason -- an empty set because
    the golden entry lists real fields none of which survive the `<` filter is
    not the same fact.
    """
    from backend.tests.contract.frontend_usage import _real_field_names

    assert _real_field_names("/api/part-opportunities/{part_number}", method="DELETE") == frozenset()
