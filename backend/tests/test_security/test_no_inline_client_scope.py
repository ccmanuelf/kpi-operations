import pathlib

ROUTES = pathlib.Path(__file__).resolve().parents[1].parent / "routes"


def test_no_route_reintroduces_buggy_scope_block():
    """No route may reintroduce the trust-the-caller / poweruser-omitting client-scope block.
    All client scoping goes through resolve_client_scope / verify_client_access now."""
    block = 'current_user.role != "admin" and current_user.client_id_assigned'
    offenders = [str(p.relative_to(ROUTES)) for p in ROUTES.rglob("*.py") if block in p.read_text()]
    assert offenders == [], f"buggy inline client-scope block still present in: {offenders}"
