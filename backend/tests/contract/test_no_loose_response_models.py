def test_no_api_route_has_a_loose_response_model():
    """Ratchet. ALLOWLIST is the work remaining; it must only ever shrink.

    A route absent from both the allowlist and the converted set fails here —
    which is what stops a new loose route being added while this refactor is in
    flight, the failure mode that would make the whole exercise pointless.

    `routes_needing_a_response_model`, not raw `loose_routes`: Task 10 scoped
    17 `/api/export` + `/api/reports/*/{pdf,excel}` routes, plus 5 `/api/qr`
    routes folded in on review (same class -- all `-> Response`, already
    `response_model=None`, orphaned from every Task 11-14 grouping), OUT of
    this ratchet entirely (none of the 22 reach Pydantic, so none can leak a
    Decimal) — see `response_scope.py` for the two-sided gate that keeps
    that exemption honest.
    """
    from backend.main import app
    from backend.tests.contract.allowlist import ALLOWLIST
    from backend.tests.contract.response_scope import routes_needing_a_response_model

    still_loose = {f"{m} {p}" for m, p, _ in routes_needing_a_response_model(app)}
    unexpected = sorted(still_loose - ALLOWLIST)
    assert unexpected == []

    stale = sorted(ALLOWLIST - still_loose)
    assert stale == [], "these are converted — remove them from ALLOWLIST"
