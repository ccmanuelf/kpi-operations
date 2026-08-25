"""Records the SHAPE of an API response — its key paths, never its values.

Values change on every reseed; shapes do not. A value-sensitive record would
churn constantly and be ignored within a week.
"""

import typing
from datetime import datetime

from pydantic import RootModel
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


class ShiftActivePin(datetime):
    """Deterministic stand-in for `datetime.now()` inside
    `backend.routes.reference`, whose only caller
    (`get_active_shift` -> `GET /api/shifts/active`) does
    `datetime.now(tz=timezone.utc).time()` and branches on which seeded
    shift, if any, contains that time-of-day. Golden-master capture used to
    read the REAL wall clock, so the recorded shape (a shift dict, or
    `<status:404>` when none is active) depended on what hour the suite
    happened to run at -- flaky by construction, not by bad luck.

    `smoke` seeds 2 shifts/client, 8 hours each, starting at hour 6 and hour
    18 UTC (see `seed/emitters_master.py`'s `shift_hour_step` derivation:
    `shift_hour_step = 24 // shifts_per_client = 12`, so shift N starts at
    `(6 + N*12) % 24`). Every client gets the SAME two windows -- 06:00-14:00
    and 18:00-02:00 -- so the union across all clients (what an unscoped
    admin sees) leaves exactly two dead zones with no shift active for
    anyone: 02:00-06:00 and 14:00-18:00 UTC. `PIN_HOUR_UTC = 15` sits inside
    the second, so the pinned capture always resolves to `<status:404>`,
    matching the currently-committed golden entry.

    Only the TIME-OF-DAY is overridden, not the date: `get_active_shift`
    calls `.time()` on the result and never reads the date component at all,
    so keeping the real date live is free correctness (no risk of the
    rolling-window date-drift a full `freeze_time`-style pin would cause
    elsewhere) rather than a compromise. `_real_now` is a class attribute,
    not a hardcoded call, specifically so a test can swap it to a fixed
    instant and prove determinism without waiting for a real clock to move
    -- see `test_time_determinism.py`.
    """

    PIN_HOUR_UTC = 15

    _real_now = datetime.now

    @classmethod
    def now(cls, tz: Any = None) -> "ShiftActivePin":
        real = cls._real_now(tz)
        return cls(real.year, real.month, real.day, cls.PIN_HOUR_UTC, 0, 0, 0, tzinfo=real.tzinfo)


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

    # A Pydantic RootModel wraps a single `root` field, and get_origin() sees a
    # plain class and returns None -- so without this it hides whatever it holds,
    # the same "cannot see through a wrapper" shape as the string-prefix bug this
    # function replaced. Dormant today (no RootModel is used as a response model
    # anywhere), but this refactor is exactly the context in which someone might
    # reach for one while "fixing" a loose route, and it would then escape both
    # the work list and the ratchet.
    if isinstance(response_model, type) and issubclass(response_model, RootModel):
        root_field = response_model.model_fields.get("root")
        if root_field is not None:
            return is_loose(root_field.annotation)

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
