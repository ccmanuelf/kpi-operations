def test_no_api_route_has_a_loose_response_model():
    """Ratchet. ALLOWLIST is the work remaining; it must only ever shrink.

    A route absent from both the allowlist and the converted set fails here —
    which is what stops a new loose route being added while this refactor is in
    flight, the failure mode that would make the whole exercise pointless.
    """
    from backend.main import app
    from backend.tests.contract.capture import loose_routes
    from backend.tests.contract.allowlist import ALLOWLIST

    still_loose = {f"{m} {p}" for m, p, _ in loose_routes(app)}
    unexpected = sorted(still_loose - ALLOWLIST)
    assert unexpected == []

    stale = sorted(ALLOWLIST - still_loose)
    assert stale == [], "these are converted — remove them from ALLOWLIST"
