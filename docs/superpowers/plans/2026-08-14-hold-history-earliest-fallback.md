# Earliest-Transition Fallback Implementation Plan (Cycle 4 PR-C1b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a hold has history but none before the as-of cutoff, resolve its status from the earliest transition's `from_status` instead of falling back to today's status.

**Architecture:** One additional correlated scalar subquery inside `active_as_of`, folded into a three-argument `COALESCE`. No schema change, no new index, no new module.

**Tech Stack:** SQLAlchemy 2.x, pytest. SQLite (dev/CI) and MariaDB 11.4 (production).

**Spec:** `docs/superpowers/specs/2026-08-13-hold-status-history-design.md`, "Amendment (2026-08-14): earliest-transition fallback — PR-C1b"

## Global Constraints

- Resolution order is exactly: (1) `to_status` of the latest transition strictly **before** the cutoff; (2) else `from_status` of the earliest transition **at or after** the cutoff; (3) else `HoldEntry.hold_status`.
- Tier 2 orders **ascending** and tie-breaks `(transitioned_at ASC, transition_id ASC)` — the mirror of tier 1's descending order, for the same MariaDB whole-second reason.
- `active_as_of` stays a composable `ColumnElement[bool]`. No Python-side filtering; its four callers depend on index-assisted `ORDER BY … LIMIT`.
- The date arm (`hold_date < cutoff`) and resume arm (`resume_date IS NULL OR resume_date >= cutoff`) are **unchanged**.
- `NON_WIP_HOLD_STATUSES` membership is unchanged.
- No new index: `ix_hold_transition_hold_asof (hold_entry_id, transitioned_at, transition_id)` already serves both scan directions.
- **As-of-now behaviour must not move.** PR-C1's golden-master invariance test must pass unchanged, untouched.
- Portable SQL only: plain comparisons against a bound datetime; no dialect-specific date arithmetic, no window functions.
- Permissive assertions are forbidden: never `assert x in [...]`; one exact expected value per assertion.
- Backend tests run as `pytest tests/` from `backend/`. Run them in the FOREGROUND; the Bash tool defaults to a 120s timeout, so pass `timeout: 900000` explicitly for the full suite.
- A test counts as evidence only after you have watched it fail for the reason it exists.

---

### Task 1: Three-tier resolution in `active_as_of`

**Files:**
- Modify: `backend/calculations/wip_aging.py` (`active_as_of` body and docstring)
- Test: `backend/tests/test_calculations/test_hold_status_history.py` (append)

**Interfaces:**
- Consumes: `HoldStatusTransition`, `snapshot_cutoff`, `NON_WIP_HOLD_STATUSES` — all unchanged.
- Produces: `active_as_of(as_of: date) -> ColumnElement[bool]`, signature unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_calculations/test_hold_status_history.py`. Follow the file's existing fixture style (file-local fixtures via `TestDataFactory`, the real `db_session` fixture, the module-level `_make_hold` helper and `_t` transition helper already defined there).

```python
@pytest.fixture
def hold_with_only_later_history(db_session, sample_client):
    """Two holds, each with history that begins AFTER the as-of date.

    Their earliest transition's `from_status` proves what they were before it,
    and it disagrees with their current status in both directions -- so tier 2
    and tier 3 cannot produce the same answer.
    """
    # Was ON_HOLD through March; cancelled in August.
    a = _make_hold(db_session, sample_client, "H-LATER-CANCELLED", datetime(2026, 2, 1, 8, 0, 0), "CANCELLED")
    # Was CANCELLED through March; re-opened in August.
    b = _make_hold(db_session, sample_client, "H-LATER-REOPENED", datetime(2026, 2, 1, 9, 0, 0), "ON_HOLD")
    db_session.flush()

    _t(db_session, a.hold_entry_id, a.client_id, "ON_HOLD", "CANCELLED", datetime(2026, 8, 8, 10, 0, 0))
    _t(db_session, b.hold_entry_id, b.client_id, "CANCELLED", "ON_HOLD", datetime(2026, 8, 8, 11, 0, 0))
    db_session.flush()

    return SimpleNamespace(later_cancelled=a.hold_entry_id, later_reopened=b.hold_entry_id)


def test_earliest_from_status_wins_over_current_status(db_session, hold_with_only_later_history):
    """Tier 2: no transition before the cutoff, but the earliest one records
    what the hold WAS. Current status is the wrong answer in both directions."""
    active = _active_ids(db_session, date(2026, 3, 3))

    # Was ON_HOLD in March even though it reads CANCELLED today.
    assert hold_with_only_later_history.later_cancelled in active
    # Was CANCELLED in March even though it reads ON_HOLD today.
    assert hold_with_only_later_history.later_reopened not in active


def test_after_that_transition_tier_one_takes_over(db_session, hold_with_only_later_history):
    """Past the August transition, tier 1 governs again and the answers flip."""
    active = _active_ids(db_session, date(2026, 8, 9))

    assert hold_with_only_later_history.later_cancelled not in active
    assert hold_with_only_later_history.later_reopened in active


def test_creation_row_from_status_null_falls_through_to_tier_three(db_session, sample_client):
    """A hold whose earliest transition is its creation row has from_status
    NULL by construction, so tier 2 yields NULL and tier 3 must decide."""
    hold = _make_hold(db_session, sample_client, "H-CREATION-ONLY", datetime(2026, 5, 1, 8, 0, 0), "ON_HOLD")
    db_session.flush()
    _t(db_session, hold.hold_entry_id, hold.client_id, None, "ON_HOLD", datetime(2026, 5, 1, 8, 0, 0))
    db_session.flush()

    # Before the hold existed: the date arm excludes it regardless of status.
    assert hold.hold_entry_id not in _active_ids(db_session, date(2026, 4, 1))
    # After: tier 1 governs.
    assert hold.hold_entry_id in _active_ids(db_session, date(2026, 5, 2))
```

- [ ] **Step 2: Run them and verify the first two fail on the ASSERTION**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v --no-cov -k "earliest_from_status or tier_one_takes_over or creation_row"`

Expected: `test_earliest_from_status_wins_over_current_status` FAILS on its assertion — under the current two-tier predicate the March answers come from current status, so `later_cancelled` is absent and `later_reopened` is present, the exact inverse of what the test asserts. Paste that output into the report.

If it fails on an import or fixture error instead, fix that and re-observe before proceeding — an error is not the evidence this step exists to collect.

- [ ] **Step 3: Add tier 2 to the predicate**

In `active_as_of`, after the existing `status_as_of` subquery and before `effective_status`:

```python
    # Tier 2: no transition before the cutoff, but the EARLIEST transition
    # records what the hold was immediately before it -- and because it is the
    # earliest, that state extends backwards over all prior time, including
    # `as_of`. Reads a column already written; this is not backfill.
    # Ascending mirror of tier 1, tie-breaking on transition_id for the same
    # MariaDB whole-second reason.
    status_before_history = (
        select(HoldStatusTransition.from_status)
        .where(
            HoldStatusTransition.hold_entry_id == HoldEntry.hold_entry_id,
            HoldStatusTransition.transitioned_at >= cutoff,
        )
        .correlate(HoldEntry)
        .order_by(
            HoldStatusTransition.transitioned_at.asc(),
            HoldStatusTransition.transition_id.asc(),
        )
        .limit(1)
        .scalar_subquery()
    )
```

Then widen the COALESCE:

```python
    effective_status = func.coalesce(status_as_of, status_before_history, HoldEntry.hold_status)
```

- [ ] **Step 4: Update the BOUNDARY docstring**

Replace the BOUNDARY paragraph so it describes three tiers, keeping the OPERATIONAL CONSEQUENCE paragraph as-is. State that tier 3 now covers exactly two cases — a hold with no transitions at all, and a creation row whose `from_status` is NULL — and that `hold_status_history_started_at`'s contract is unchanged.

- [ ] **Step 5: Verify the tests pass**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v --no-cov`
Expected: all pass, including PR-C1's pre-existing tests. **The golden-master invariance test must pass untouched** — if it fails, tier 2 is matching at `as_of=today`, which means the `>= cutoff` bound is wrong. Do not edit that test to accommodate the change; fix the predicate.

- [ ] **Step 6: Prove non-vacuity**

Revert `effective_status` to the two-argument form, re-run the three new tests, confirm `test_earliest_from_status_wins_over_current_status` and `test_after_that_transition_tier_one_takes_over` behave as before the change, paste the output, restore.

- [ ] **Step 7: Run the consumers**

Run: `pytest tests/test_calculations/ tests/test_routes/test_holds_aging_portability.py --no-cov -q`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add backend/calculations/wip_aging.py backend/tests/test_calculations/test_hold_status_history.py
git commit -m "fix(kpi): resolve pre-history status from the earliest transition's from_status"
```

---

### Task 2: MariaDB portability and query-plan guard

**Files:**
- Modify: `backend/tests/test_mariadb_portability.py` (append)

**Interfaces:**
- Consumes: the three-tier `active_as_of` from Task 1.
- Produces: nothing consumed downstream.

SQLite cannot catch this repo's recurring bug class — a production `julianday()` defect once shipped with the whole SQLite suite green.

- [ ] **Step 1: Write the tests**

Follow the existing `mariadb_hold_history` fixture pattern in that file. Write microsecond-free datetimes; the column stores whole seconds.

```python
def test_earliest_from_status_fallback_executes_on_mariadb(mariadb_earliest_fallback):
    """Tier 2 adds a second correlated subquery with ORDER BY + LIMIT; it must
    execute and resolve correctly on MariaDB, not only SQLite."""
    session, ids = mariadb_earliest_fallback

    active = {h.hold_entry_id for h in session.query(HoldEntry).filter(active_as_of(date(2026, 3, 3))).all()}

    assert active == {ids["later_cancelled"]}


def test_three_tier_predicate_keeps_outer_index_on_mariadb(mariadb_earliest_fallback):
    """Two correlated subqueries must not cost the outer top-N its index.
    Explains the query built WITH active_as_of -- a literal SQL string would
    pass regardless of what the predicate does."""
    session, _ = mariadb_earliest_fallback

    query = (
        session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(session.bind, compile_kwargs={"literal_binds": True})
    plan = session.execute(text(f"EXPLAIN {compiled}")).fetchall()

    outer = [r for r in plan if r.table == "HOLD_ENTRY"]
    assert len(outer) == 1
    assert "Using filesort" not in str(outer[0].Extra or "")
```

The `mariadb_earliest_fallback` fixture mirrors Task 1's SQLite fixture against the `mariadb_schema` engine: two client-scoped holds, current statuses CANCELLED and ON_HOLD, each with a single 2026-08-08 transition whose `from_status` is the opposite. Scope every read by `client_id` — the file's convention at lines 510-514 requires it, because `mariadb_schema` is module-scoped and rows survive between tests.

- [ ] **Step 2: Run against MariaDB**

Run: `pytest tests/test_mariadb_portability.py -v --no-cov`

If the local 3306 is occupied by an unrelated instance, use a throwaway `mariadb:11.4` container on an alternate port. If MariaDB is genuinely unreachable, say so plainly and do not report an unobserved pass — CI's `mariadb-portability` job runs regardless.

- [ ] **Step 3: Run the full suite**

Run: `pytest tests/ -q` (foreground, explicit long timeout)
Expected: green, coverage ≥ 75%.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_mariadb_portability.py
git commit -m "test(kpi): MariaDB coverage for the earliest-transition fallback"
```

---

## Verification before opening the PR

- [ ] `pytest tests/` green from `backend/`, coverage ≥ 75%
- [ ] `pytest tests/test_mariadb_portability.py -v --no-cov` green against live MariaDB
- [ ] PR-C1's golden-master invariance test passes **unmodified**
- [ ] `pre-commit run --all-files` clean
- [ ] `/cross-review` run for the final HEAD — run `git checkout` as its own command before marking, never chained with `&&`, since the gate evaluates HEAD before the command runs
