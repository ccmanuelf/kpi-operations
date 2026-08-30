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

    Imported from `schema_document_routes`, not `response_scope` directly,
    since Batch R5: that module's `routes_needing_a_response_model` wraps
    `response_scope`'s and further excludes `GET /api/v2/simulation/schema`,
    a JSON-Schema-document response this refactor deliberately does not
    model -- see that module's docstring and its own two-sided gate
    (`test_schema_document_routes.py`).
    """
    from backend.main import app
    from backend.tests.contract.allowlist import ALLOWLIST
    from backend.tests.contract.schema_document_routes import routes_needing_a_response_model

    still_loose = {f"{m} {p}" for m, p, _ in routes_needing_a_response_model(app)}
    unexpected = sorted(still_loose - ALLOWLIST)
    assert unexpected == []

    stale = sorted(ALLOWLIST - still_loose)
    assert stale == [], "these are converted — remove them from ALLOWLIST"


def test_the_rty_error_shape_cannot_escape_its_404():
    """`WorkOrderRTYResponse` declares no `error` field. That is only safe
    while every error-shaped return in `calculate_work_order_job_rty` sets
    `job_count` to 0, because the route raises 404 on exactly

        "error" in result and result.get("job_count", 0) == 0

    An error return that left `job_count` non-zero would sail past the 404,
    hit the response model, and have its `error` key silently dropped --
    Pydantic ignores undeclared fields -- so the caller would receive a
    normal-looking body with rty_percentage 0 and no indication anything
    went wrong. Nothing else pins that coupling, so this reads the function's
    own AST: every `return {...}` literal carrying an "error" key must also
    carry `job_count` set to a literal 0.
    """
    import ast
    import inspect
    import textwrap

    from backend.calculations import fpy_rty

    source = textwrap.dedent(inspect.getsource(fpy_rty.calculate_work_order_job_rty))
    tree = ast.parse(source)

    error_returns = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
            continue
        keys = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
        if "error" not in keys:
            continue
        error_returns += 1
        pairs = {k.value: v for k, v in zip(node.value.keys, node.value.values) if isinstance(k, ast.Constant)}
        job_count = pairs.get("job_count")
        assert isinstance(job_count, ast.Constant) and job_count.value == 0, (
            "an error-shaped return in calculate_work_order_job_rty does not pin job_count to 0; "
            "it would bypass the route's 404 and lose its `error` key to WorkOrderRTYResponse"
        )

    # Guard the guard: if the error branch is ever removed this test is
    # vacuous, and the reasoning above should be revisited rather than left
    # passing on nothing.
    assert error_returns == 1, f"expected exactly one error-shaped return, found {error_returns}"
