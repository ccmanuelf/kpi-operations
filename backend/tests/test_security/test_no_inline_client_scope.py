import pathlib
import re

ROUTES = pathlib.Path(__file__).resolve().parents[1].parent / "routes"

# Files with a legitimate, safe use of client_id_assigned that would
# otherwise trip the broadened regex guards below. Each entry must be
# justified: the match is an assignment/read of the CALLER'S OWN client
# (never a cross-tenant `==` filter), so it cannot leak another tenant's data.
ALLOWLIST_SCALAR_EQ: dict[str, str] = {
    # (populate only if a future genuine-but-safe match is found; keep empty
    # otherwise so the guard stays maximally strict)
}
ALLOWLIST_ROLE_VARIANT: dict[str, str] = {}

# (b) scalar-scoping-by-assignment leak shape: filtering a query column
# against current_user.client_id_assigned via `==` instead of going through
# scope.filter() (reads) or verify_client_access() (writes).
SCALAR_EQ_PATTERN = re.compile(r"client_id\s*==\s*current_user\.client_id_assigned")

# (c) poweruser-omitting role-scoping variant used for filtering: checks
# role != "admin" (or 'admin') and then references client_id_assigned on the
# same logical line, silently scoping poweruser out of the "trusted" branch.
ROLE_VARIANT_PATTERN = re.compile(r"role\s*!=\s*[\"']admin[\"'].*client_id_assigned")


def _offenders(pattern: "re.Pattern[str]", allowlist: dict[str, str]) -> list[str]:
    offenders = []
    for p in ROUTES.rglob("*.py"):
        rel = str(p.relative_to(ROUTES))
        if rel in allowlist:
            continue
        text = p.read_text()
        for line in text.splitlines():
            if pattern.search(line):
                offenders.append(rel)
                break
    return offenders


def test_no_route_reintroduces_buggy_scope_block():
    """No route may reintroduce the trust-the-caller / poweruser-omitting client-scope block.
    All client scoping goes through resolve_client_scope / verify_client_access now."""
    block = 'current_user.role != "admin" and current_user.client_id_assigned'
    offenders = [str(p.relative_to(ROUTES)) for p in ROUTES.rglob("*.py") if block in p.read_text()]
    assert offenders == [], f"buggy inline client-scope block still present in: {offenders}"


def test_no_route_uses_scalar_client_id_equality_filter():
    """No route may filter a query by `<col> == current_user.client_id_assigned`.
    This is the scalar-scoping-by-assignment leak shape: it 400s a multi-client
    leader (see chronic-holds regression) or silently drops other authorized
    clients. Reads must use `scope.filter(...)`; writes must use
    `verify_client_access(...)`."""
    offenders = _offenders(SCALAR_EQ_PATTERN, ALLOWLIST_SCALAR_EQ)
    assert offenders == [], (
        f"scalar client_id == current_user.client_id_assigned filter present in: {offenders}. "
        "Migrate reads to scope.filter(...) and writes to verify_client_access(...)."
    )


def test_no_route_uses_poweruser_omitting_role_variant():
    """No route may gate client-scoping on `role != \"admin\"` (which silently
    omits poweruser from the trusted/all-clients branch) combined with
    client_id_assigned on the same line. Use resolve_client_scope's
    ClientScope, which correctly treats admin and poweruser alike."""
    offenders = _offenders(ROLE_VARIANT_PATTERN, ALLOWLIST_ROLE_VARIANT)
    assert offenders == [], f"poweruser-omitting role-scoping variant present in: {offenders}"
