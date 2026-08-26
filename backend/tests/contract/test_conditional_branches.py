"""Two mechanisms for the branches the golden master's smoke seed cannot
reach, per the Task 9 review follow-up: a declaration alone is exactly as
trustworthy as the audit that populated it, so a registry gate is only half
an answer without something that forces the branch and checks its shape.

1. The exclude_unset registry (`conditional_branches.py`) is gated two-sided
   here -- declared members must carry the flag, and nothing else may.

2. Each conditional branch that has NO other coverage gets a forcing test:
   build the branch's dict directly (the same `Mock()` pattern as the
   existing unit tests in tests/test_calculations/test_workflow_elapsed_time.py),
   and check it TWICE -- once as the raw dict the producing function
   actually returned, once as what the model emits after validation.

   THE TRAP, found by review on the first version of this file: asserting
   only the validated/dumped side is blind to an ADDED field. Pydantic
   silently discards keys the model does not declare, so
   `Model(**raw).model_dump()` never shows a stray key even when `raw`
   carries one -- the branch's shape could grow silently and every
   assertion here would still pass. Validating through the model erases
   exactly the evidence a shape-regression test is trying to inspect. Any
   test that checks a shape by round-tripping it through the thing whose
   job is to NORMALISE that shape will be blind in the direction that
   normalisation discards. The fix is to inspect the raw value first --
   `set(raw.keys()) == {...}` -- and the normalised one second; the raw
   assertion is what catches an added field, the dumped assertion is what
   catches the model silently dropping a field it used to declare or
   `exclude_unset` doing the wrong thing.

`stage_durations`' non-empty interior is NOT an exclude_unset case --
`calculate_stage_duration_summary` never omits a key, it returns a list that
is empty or not, and an empty list is a value, not an omitted key. It gets a
forcing test here anyway because its golden entry is a bare, childless key
(no captured evidence for the interior at all), so this test is the only
thing standing behind `StageDurationEntry`'s shape. It round-trips through a
model the same way `average-times` does, so it carries the same trap and
gets the same two-assertion treatment.
"""

import asyncio
from unittest.mock import Mock, patch

from backend.calculations.elapsed_time import (
    calculate_client_average_times,
    calculate_stage_duration_summary,
)
from backend.routes.cache import cache_health
from backend.schemas.ops_contracts import CacheHealthResponse
from backend.schemas.workflow_contracts import AverageTimesSummary, StageDurationsResponse
from backend.tests.contract.conditional_branches import EXCLUDE_UNSET_ROUTES, declared_exclude_unset_routes


def test_exclude_unset_flag_matches_the_declared_registry():
    """Two-sided: a route dropping the flag without updating the registry
    fails here (declared member no longer actual), and a route gaining the
    flag without anyone writing down why also fails here (actual member not
    declared). A one-sided version -- checking only that declared members
    carry the flag -- would pass with EXCLUDE_UNSET_ROUTES empty, which is
    exactly the state this test exists to make impossible.
    """
    from backend.main import app

    assert declared_exclude_unset_routes(app) == frozenset(EXCLUDE_UNSET_ROUTES)


def test_average_times_empty_orders_branch_omits_overdue_keys():
    """Forces GET /api/workflow/analytics/{client_id}/average-times' zero-
    work-orders branch and pins its exact key set, on BOTH sides of
    validation.

    The golden master cannot do this at all: its captured client has work
    orders, so removing response_model_exclude_unset=True from the route
    does NOT fail test_no_route_lost_a_field (confirmed empirically by the
    reviewer -- the suite stayed 43/43 green). This test is what catches a
    key being REMOVED from the branch (either assertion) and what catches a
    key being ADDED to it (the raw-dict assertion only -- the dumped
    assertion cannot see an added key at all, since Pydantic discards
    whatever the model does not declare before `dumped` exists).
    """
    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []

    raw = calculate_client_average_times(mock_db, "CLIENT-001")
    # The branch's real shape, before anything normalises it away.
    assert set(raw.keys()) == {"client_id", "count", "averages"}
    assert raw == {"client_id": "CLIENT-001", "count": 0, "averages": None}

    dumped = AverageTimesSummary(**raw).model_dump(exclude_unset=True)
    # What the model actually emits over the wire.
    assert set(dumped.keys()) == {"client_id", "count", "averages"}
    assert dumped == {"client_id": "CLIENT-001", "count": 0, "averages": None}


def test_stage_durations_non_empty_interior_pins_its_key_set():
    """Forces one real (non-empty) `stage_durations` row and pins
    StageDurationEntry's exact key set, on BOTH sides of validation -- the
    golden master's captured entry is a bare `stage_durations` key with no
    dotted children (smoke seed has zero grouped WORKFLOW_TRANSITION_LOG
    rows), so there is no other committed evidence for this interior at
    all. See the module docstring for why both the raw dict and the
    validated model are checked separately.
    """
    mock_result = Mock()
    mock_result.from_status = "RECEIVED"
    mock_result.to_status = "RELEASED"
    mock_result.avg_hours = 4.5
    mock_result.min_hours = 2
    mock_result.max_hours = 8
    mock_result.count = 10

    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.all.return_value = [mock_result]

    raw = calculate_stage_duration_summary(mock_db, "CLIENT-001")
    raw_entry = raw["stage_durations"][0]
    # The branch's real shape, before anything normalises it away.
    assert set(raw_entry.keys()) == {
        "from_status",
        "to_status",
        "avg_hours",
        "avg_days",
        "min_hours",
        "max_hours",
        "transition_count",
    }
    assert raw_entry == {
        "from_status": "RECEIVED",
        "to_status": "RELEASED",
        "avg_hours": 4.5,
        "avg_days": 0.19,
        "min_hours": 2,
        "max_hours": 8,
        "transition_count": 10,
    }

    validated = StageDurationsResponse(**raw)
    entry = validated.stage_durations[0].model_dump()
    # What the model actually emits over the wire.
    assert set(entry.keys()) == {
        "from_status",
        "to_status",
        "avg_hours",
        "avg_days",
        "min_hours",
        "max_hours",
        "transition_count",
    }
    assert entry == raw_entry


def test_cache_health_error_branch_omits_entries_and_hit_rate():
    """Forces GET /api/cache/health's `except Exception` branch (routes/cache.py
    ::cache_health) by making `get_cache()` raise, and pins its exact 3-key
    shape on BOTH sides of validation -- the golden master cannot do this at
    all, since the in-memory cache never organically raises, so a captured
    entry only ever shows the 4-key success shape.

    Calls the real route coroutine directly (`asyncio.run`), the same
    "build the branch, don't hand-copy it" approach as
    `test_average_times_empty_orders_branch_omits_overdue_keys` -- patching
    a dependency to force a branch, not re-typing the branch's literal.
    """
    with patch("backend.routes.cache.get_cache", side_effect=RuntimeError("boom")):
        raw = asyncio.run(cache_health())

    # The branch's real shape, before anything normalises it away.
    assert set(raw.keys()) == {"status", "timestamp", "error"}
    assert raw["status"] == "error"
    assert raw["error"] == "Cache health check failed"

    dumped = CacheHealthResponse(**raw).model_dump(exclude_unset=True)
    # What the model actually emits over the wire.
    assert set(dumped.keys()) == {"status", "timestamp", "error"}
    assert dumped == raw
