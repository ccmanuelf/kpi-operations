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
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from backend.calculations.elapsed_time import (
    calculate_client_average_times,
    calculate_stage_duration_summary,
)
from backend.calculations.fpy_rty import calculate_job_rty_summary
from backend.crud.floating_pool.assignments import is_employee_available_for_assignment
from backend.routes.alerts.config_history import get_prediction_accuracy
from backend.routes.cache import cache_health
from backend.routes.work_orders import approve_qc
from backend.schemas.floor_contracts import FloatingPoolCheckAvailabilityResponse
from backend.schemas.kpi_metrics_contracts import JobRTYSummaryResponse
from backend.schemas.ops_contracts import CacheHealthResponse
from backend.schemas.workflow_contracts import AverageTimesSummary, StageDurationsResponse
from backend.schemas.workorder_contracts import AlertsHistoryAccuracyResponse, WorkOrderApproveQCResponse
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


def test_prediction_accuracy_non_empty_history_branch_omits_the_other_shape():
    """Forces GET /api/alerts/history/accuracy's non-empty-history branch
    (routes/alerts/config_history.py::get_prediction_accuracy) and pins its
    exact 6-key shape on BOTH sides of validation -- the golden master's
    captured entry is the OTHER, entirely disjoint branch (zero ALERT_HISTORY
    rows with a non-null actual_value in the lookback window), so there is
    no other coverage for this branch, or proof that `accuracy_metrics`/
    `message` are correctly absent from it, at all.
    """
    mock_history_row = Mock()
    mock_history_row.was_accurate = True
    mock_history_row.error_percent = 5.0

    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_history_row]

    mock_db = Mock()
    mock_db.query.return_value = mock_query

    raw = asyncio.run(get_prediction_accuracy(days=30, category=None, db=mock_db, current_user=Mock()))

    # The branch's real shape, before anything normalises it away.
    assert set(raw.keys()) == {
        "period_days",
        "total_predictions",
        "accurate_predictions",
        "accuracy_rate_percent",
        "average_error_percent",
        "category",
    }
    assert raw == {
        "period_days": 30,
        "total_predictions": 1,
        "accurate_predictions": 1,
        "accuracy_rate_percent": 100.0,
        "average_error_percent": 5.0,
        "category": "all",
    }

    dumped = AlertsHistoryAccuracyResponse(**raw).model_dump(exclude_unset=True)
    # What the model actually emits over the wire -- "accuracy_metrics" and
    # "message" (the OTHER branch's fields) must not leak in as nulls.
    assert set(dumped.keys()) == set(raw.keys())
    assert dumped == raw


def test_approve_qc_already_approved_branch_omits_message():
    """Forces POST /api/work-orders/{work_order_id}/approve-qc's already-
    approved branch (routes/work_orders.py::approve_qc) and pins its exact
    5-key shape on BOTH sides of validation -- the golden master's captured
    entry is the 6-key freshly-approved branch (the isolated-capture harness
    calls this route exactly once per restored snapshot, so it always lands
    on that first-approval path); the already-approved branch, reached only
    on a SECOND call against the same work order, has no other coverage.
    """
    mock_work_order = Mock()
    mock_work_order.qc_approved = True
    mock_work_order.qc_approved_date = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    mock_work_order.qc_approved_by = "user-1"

    with patch("backend.routes.work_orders.get_work_order", return_value=mock_work_order):
        raw = approve_qc(work_order_id="WO-1", approval_data=None, db=Mock(), current_user=Mock())

    # The branch's real shape, before anything normalises it away.
    assert set(raw.keys()) == {"status", "work_order_id", "qc_approved", "qc_approved_date", "qc_approved_by"}
    assert raw == {
        "status": "already_approved",
        "work_order_id": "WO-1",
        "qc_approved": True,
        "qc_approved_date": "2026-08-27T12:00:00+00:00",
        "qc_approved_by": "user-1",
    }

    dumped = WorkOrderApproveQCResponse(**raw).model_dump(exclude_unset=True)
    # What the model actually emits over the wire -- "message" (the OTHER
    # branch's field) must not leak in as null.
    assert set(dumped.keys()) == set(raw.keys())
    assert dumped == raw


def test_check_availability_existing_assignment_populates_conflict_dates():
    """Forces GET /api/floating-pool/check-availability/{employee_id}'s
    existing-assignment branch (crud/floating_pool/assignments.py::
    is_employee_available_for_assignment) and pins its exact 4-key shape on
    BOTH sides of validation -- HAZARD 2 (task-R3-brief.md): this route is
    id-insensitive (`NEVER_404`, param_specs.py) and its ONLY captured
    evidence is the no-existing-assignment floor
    (`current_assignment`/`conflict_dates` both null), so the POPULATED
    shape `FloatingPoolCheckAvailabilityResponse` claims to support has no
    other coverage at all.
    """
    mock_assignment = Mock()
    mock_assignment.current_assignment = "CLIENT-002"
    mock_assignment.available_from = datetime(2026, 8, 1, tzinfo=timezone.utc)
    mock_assignment.available_to = datetime(2026, 8, 15, tzinfo=timezone.utc)

    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_assignment

    mock_db = Mock()
    mock_db.query.return_value = mock_query

    raw = is_employee_available_for_assignment(mock_db, employee_id=42)

    # The branch's real shape, before anything normalises it away.
    assert set(raw.keys()) == {"is_available", "current_assignment", "conflict_dates", "message"}
    assert raw == {
        "is_available": False,
        "current_assignment": "CLIENT-002",
        "conflict_dates": {
            "existing_start": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "existing_end": datetime(2026, 8, 15, tzinfo=timezone.utc),
        },
        "message": "Employee is currently assigned to 'CLIENT-002'",
    }

    dumped = FloatingPoolCheckAvailabilityResponse(**raw).model_dump()
    # What the model actually emits over the wire -- plain model_dump(), not
    # exclude_unset=True: this route does not carry response_model_
    # exclude_unset (correctly -- all 4 keys are always present, never
    # omitted). Using exclude_unset here would hide a field this model
    # declares but this branch never populates, shipping as a spurious
    # `null` in production while this assertion stayed green.
    assert set(dumped.keys()) == set(raw.keys())
    assert dumped == raw


def test_jobs_rty_summary_populated_branch_pins_the_extra_keys():
    """Forces GET /api/jobs/kpi/rty-summary's non-empty-jobs branch
    (calculations/fpy_rty.py::calculate_job_rty_summary) and pins the three
    keys ABSENT from the empty-jobs branch the golden master actually
    captured (total_good_units, jobs_meeting_target, interpretation) -- the
    smoke seed has zero Job rows completed in the trailing-30-day window at
    capture time, so the golden entry is the empty branch's 8-key shape (9
    golden leaf paths -- `period` flattens into `period.start_date`/
    `period.end_date`) and offers no evidence these three keys exist, or of
    their types, at all.
    """
    mock_job = Mock()
    mock_job.completed_quantity = 100
    mock_job.quantity_scrapped = 5
    mock_job.operation_name = "Assembly"

    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_job]

    mock_db = Mock()
    mock_db.query.return_value = mock_query

    raw = calculate_job_rty_summary(mock_db, date(2026, 8, 1), date(2026, 8, 27))

    # The branch's real shape, before anything normalises it away.
    assert set(raw.keys()) == {
        "period",
        "total_jobs_completed",
        "total_units_completed",
        "total_units_scrapped",
        "total_good_units",
        "average_job_yield",
        "overall_yield",
        "jobs_below_target",
        "jobs_meeting_target",
        "top_scrap_operations",
        "interpretation",
    }
    assert raw["total_good_units"] == 95
    assert raw["jobs_meeting_target"] == 1
    assert raw["interpretation"] == "Good: Meeting standard targets"

    dumped = JobRTYSummaryResponse(**raw).model_dump(exclude_unset=True)
    # What the model actually emits over the wire.
    assert set(dumped.keys()) == set(raw.keys())
    assert dumped["total_good_units"] == 95
    assert dumped["jobs_meeting_target"] == 1
    assert dumped["interpretation"] == "Good: Meeting standard targets"
