import json
import os
from typing import Any

from backend.main import app

SNAP = os.path.join(os.path.dirname(__file__), "openapi_surface.json")


def current_surface() -> dict[str, Any]:
    routes = sorted([m, getattr(r, "path", "")] for r in app.routes for m in (getattr(r, "methods", None) or []))
    tags = [t["name"] for t in app.openapi().get("tags", [])]
    return {"routes": routes, "tags": tags}


def test_openapi_tag_set_unchanged():
    expected = json.load(open(SNAP))
    assert current_surface()["tags"] == expected["tags"]


def test_openapi_route_set_unchanged():
    expected = json.load(open(SNAP))
    assert current_surface()["routes"] == expected["routes"]
