import json
import os
from typing import Any

from backend.main import app

SNAP = os.path.join(os.path.dirname(__file__), "openapi_surface.json")


def _effective_routes(routes):
    """Yield the fully-resolved routes behind FastAPI's include wrappers.

    ``include_router`` holds each include as a wrapper whose own ``path``/
    ``methods`` are ``None`` and which exposes ``effective_route_contexts()`` to
    expand it into the underlying routes with their prefixes already applied.
    Detect that wrapper by duck-typing on the method (avoids importing FastAPI's
    private ``_IncludedRouter``); plain routes (the app-level ``/``, ``/docs``,
    mounts, …) are yielded as-is. This recovers the same flat (method, path)
    surface FastAPI exposed before the include restructuring, so the golden
    master keeps validating an *unchanged* surface.
    """
    for route in routes:
        expand = getattr(route, "effective_route_contexts", None)
        if callable(expand):
            yield from expand()
        else:
            yield route


def current_surface() -> dict[str, Any]:
    routes = sorted(
        [m, getattr(r, "path", "")] for r in _effective_routes(app.routes) for m in (getattr(r, "methods", None) or [])
    )
    tags = [t["name"] for t in app.openapi().get("tags", [])]
    return {"routes": routes, "tags": tags}


def test_openapi_tag_set_unchanged():
    with open(SNAP) as f:
        expected = json.load(f)
    assert current_surface()["tags"] == expected["tags"]


def test_openapi_route_set_unchanged():
    with open(SNAP) as f:
        expected = json.load(f)
    assert current_surface()["routes"] == expected["routes"]
