def test_no_api_route_has_a_loose_response_model():
    """Ratchet. ALLOWLIST is the work remaining; it must only ever shrink.

    A route absent from both the allowlist and the converted set fails here —
    which is what stops a new loose route being added while this refactor is in
    flight, the failure mode that would make the whole exercise pointless.

    `routes_needing_a_response_model`, not raw `loose_routes`: Task 10 scoped
    17 `/api/export` + `/api/reports/*/{pdf,excel}` routes OUT of this
    ratchet entirely (they return `StreamingResponse`, never Pydantic, so
    they can never leak a Decimal) — see `response_scope.py` for the
    two-sided gate that keeps that exemption honest.
    """
    from backend.main import app
    from backend.tests.contract.allowlist import ALLOWLIST
    from backend.tests.contract.response_scope import routes_needing_a_response_model

    still_loose = {f"{m} {p}" for m, p, _ in routes_needing_a_response_model(app)}
    unexpected = sorted(still_loose - ALLOWLIST)
    assert unexpected == []

    stale = sorted(ALLOWLIST - still_loose)
    assert stale == [], "these are converted — remove them from ALLOWLIST"
