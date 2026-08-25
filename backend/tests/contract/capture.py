"""Records the SHAPE of an API response — its key paths, never its values.

Values change on every reseed; shapes do not. A value-sensitive record would
churn constantly and be ignored within a week.
"""

import typing
from typing import Any, List

from fastapi.routing import APIRoute

#: Fields whose dict KEYS are data, not field names -- a value->count map rather
#: than an object with fixed attributes. `shape_of` records these as `field.*`
#: and never recurses into their keys.
#:
#: Without this, /api/alerts/dashboard records `by_severity.critical` only while
#: a critical alert happens to be active, so the SAME endpoint with UNCHANGED
#: code yields a different shape between captures -- and a severity with zero
#: active alerts is indistinguishable from a dropped field. That is precisely
#: the signal this harness exists to give, so the harness must not manufacture
#: false ones.
#:
#: CANNOT be derived: nothing in the payload distinguishes {"critical": 2} from
#: an object with a "critical" attribute. It is listed, and pinned by
#: test_map_fields_are_exactly_the_known_five so a new one is a deliberate act.
MAP_FIELDS = frozenset(
    {
        "by_severity",  # GET /api/alerts/dashboard, /api/alerts/summary
        "by_category",  # GET /api/alerts/dashboard, /api/alerts/summary
        "weekly_demand",  # POST /api/v2/simulation/plan-horizon
        "pieces_by_product",  # POST /api/v2/simulation/plan-horizon
        "fulfillment_by_product",  # POST /api/v2/simulation/plan-horizon
    }
)


def shape_of(payload: Any, prefix: str = "") -> List[str]:
    """Sorted dotted key paths. A list contributes `name[]` and recurses into
    its FIRST element only — homogeneous collections are the norm here, and
    walking every row would make the record depend on how much data was seeded.
    """
    keys: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in MAP_FIELDS:
                # Treated like a list: one stable entry, recursing into the first
                # VALUE so a map of objects still has its inner shape recorded,
                # while the data-derived keys never reach the record.
                inner = next(iter(value.values()), None) if isinstance(value, dict) and value else None
                child = shape_of(inner, f"{path}.*") if inner is not None else []
                keys.extend(child if child else [f"{path}.*"])
                continue
            child = shape_of(value, path)
            keys.extend(child if child else [path])
    elif isinstance(payload, list):
        if payload:
            child = shape_of(payload[0], f"{prefix}[]")
            keys.extend(child if child else [f"{prefix}[]"])
    return sorted(set(keys))


def capture_all(client, routes) -> dict:
    """Exercise every route and record its shape.

    `routes` is a list of (method, path, kwargs) prepared by the caller, which
    owns id resolution — the harness deliberately does not guess ids, because a
    wrong id yields a 404 whose shape is recorded as if it were the real answer.
    """
    captured = {}
    for method, path, kwargs in routes:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            captured[f"{method} {path}"] = [f"<status:{response.status_code}>"]
            continue
        try:
            captured[f"{method} {path}"] = shape_of(response.json())
        except ValueError:
            captured[f"{method} {path}"] = ["<non-json>"]
    return captured


def is_loose(response_model) -> bool:
    """True when the declared model cannot constrain a Decimal.

    `None`, `Any`, and bare `dict`/`list` all let Pydantic serialise a Decimal as
    a JSON string. So does any wrapper around one of those -- `List[dict]`,
    `Optional[dict]`, `Dict[str, Any]` -- because the wrapper constrains the
    container, not the values inside it.

    STRUCTURAL, via get_origin/get_args, NOT a string match on the repr. The
    first version of this predicate did `str(model).startswith(("typing.Any",
    "dict", "list[dict", ...))`, which cannot see through a wrapper: wrapping
    moves the marker away from position 0, so `typing.List[dict]` tested as
    TYPED. That silently dropped four live routes -- GET /api/products,
    GET /api/shifts, GET /api/shifts/active and
    GET /api/workflow/work-orders/{work_order_id}/transition-times -- from both
    the refactor's work list and the ratchet allowlist, where nothing would ever
    have flagged them again. `typing.List[...]` is the dominant annotation style
    in this codebase, so the blind spot was aimed squarely at the common case.
    """
    if response_model is None:
        return True
    if response_model in (typing.Any, dict, list):
        return True

    origin = typing.get_origin(response_model)
    if origin is None:
        return False

    # Optional[X] is Union[X, None]; X | None has a different origin in 3.11+.
    args = [a for a in typing.get_args(response_model) if a is not type(None)]
    if not args:
        # A bare `List`/`Dict` with no parameters constrains nothing.
        return True
    return any(is_loose(a) for a in args)


def loose_routes(app) -> list:
    found: List[tuple] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        if not is_loose(route.response_model):
            continue
        for method in sorted(set(route.methods) - {"HEAD", "OPTIONS"}):
            found.append((method, route.path, {}))
    return found
