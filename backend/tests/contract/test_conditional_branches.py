"""Two mechanisms for the branches the golden master's smoke seed cannot
reach, per the Task 9 review follow-up: a declaration alone is exactly as
trustworthy as the audit that populated it, so a registry gate is only half
an answer without something that forces the branch and checks its shape.

1. The exclude_unset registry (`conditional_branches.py`) is gated two-sided
   here -- declared members must carry the flag, and nothing else may.

2. Each conditional branch that has NO other coverage gets a forcing test:
   build the branch's dict directly (the same `Mock()` pattern as the
   existing unit tests in tests/test_calculations/test_workflow_elapsed_time.py),
   validate it against the real model, and pin the EXACT key set. This is
   the half that actually catches a regression -- the registry gate above
   only catches someone removing or adding the flag, not the branch's shape
   changing under it.

`stage_durations`' non-empty interior is NOT an exclude_unset case --
`calculate_stage_duration_summary` never omits a key, it returns a list that
is empty or not, and an empty list is a value, not an omitted key. It gets a
forcing test here anyway because its golden entry is a bare, childless key
(no captured evidence for the interior at all), so this test is the only
thing standing behind `StageDurationEntry`'s shape.
"""

from unittest.mock import Mock

from backend.calculations.elapsed_time import (
    calculate_client_average_times,
    calculate_stage_duration_summary,
)
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
    work-orders branch and pins its exact key set.

    The golden master cannot do this: its captured client has work orders,
    so removing response_model_exclude_unset=True from the route does NOT
    fail test_no_route_lost_a_field (confirmed empirically by the reviewer --
    the suite stayed 43/43 green). THIS test is what actually fails if the
    branch's shape regresses.
    """
    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []

    raw = calculate_client_average_times(mock_db, "CLIENT-001")
    dumped = AverageTimesSummary(**raw).model_dump(exclude_unset=True)

    assert set(dumped.keys()) == {"client_id", "count", "averages"}
    assert dumped == {"client_id": "CLIENT-001", "count": 0, "averages": None}


def test_stage_durations_non_empty_interior_pins_its_key_set():
    """Forces one real (non-empty) `stage_durations` row and pins
    StageDurationEntry's exact key set -- the golden master's captured entry
    is a bare `stage_durations` key with no dotted children (smoke seed has
    zero grouped WORKFLOW_TRANSITION_LOG rows), so there is no other
    committed evidence for this interior at all.
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
    validated = StageDurationsResponse(**raw)
    entry = validated.stage_durations[0].model_dump()

    assert set(entry.keys()) == {
        "from_status",
        "to_status",
        "avg_hours",
        "avg_days",
        "min_hours",
        "max_hours",
        "transition_count",
    }
    assert entry == {
        "from_status": "RECEIVED",
        "to_status": "RELEASED",
        "avg_hours": 4.5,
        "avg_days": 0.19,
        "min_hours": 2,
        "max_hours": 8,
        "transition_count": 10,
    }
