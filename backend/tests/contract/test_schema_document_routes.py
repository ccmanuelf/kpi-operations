"""Two-sided gate for `schema_document_routes.SCHEMA_DOCUMENT_ROUTES` -- see
that module's docstring for what the exemption claims and why it is not the
same claim `response_scope.OUT_OF_SCOPE_ROUTES` makes.
"""

from __future__ import annotations

import json

from backend.tests.contract.capture import shape_of
from backend.tests.contract.conftest import GOLDEN
from backend.tests.contract.schema_document_routes import (
    SCHEMA_DOCUMENT_ROUTES,
    routes_needing_a_response_model,
)


def test_declared_schema_document_route_matches_its_models_own_json_schema():
    """Forward side: the golden shape for each declared route is EXACTLY
    `shape_of(<model>.model_json_schema())` -- proof the route emits
    Pydantic's own schema output, not something this refactor invented or
    should be modeling by hand. A route that started returning anything
    else -- even a same-sized hand-built dict -- fails here by name.
    """
    golden = json.loads(GOLDEN.read_text())
    for route_key, entry in SCHEMA_DOCUMENT_ROUTES.items():
        assert golden[route_key] == shape_of(entry.model.model_json_schema()), route_key


def test_schema_document_route_is_absent_from_the_remaining_ratchet_scope():
    """Reverse side: the declared route no longer appears in what still
    needs a response model -- this registry, not oversight, is why."""
    from backend.main import app

    still_needing = {f"{m} {p}" for m, p, _ in routes_needing_a_response_model(app)}
    assert still_needing.isdisjoint(SCHEMA_DOCUMENT_ROUTES)
