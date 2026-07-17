# Seeder Realistic Shift-Time Timestamps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Timestamp seeded operational entries at their shift's start time (06:00) instead of midnight, so demo data is realistic and the #145 date-range boundary fix is demonstrable on live data.

**Architecture:** Replace `datetime.min.time()` with `shift.start_time` at the two `day_dt` sites in `seed_daily_data`; add a test pinning the non-midnight timestamp.

**Tech Stack:** Python, SQLAlchemy, pytest.

## Global Constraints

- Only the two `day_dt = datetime.combine(day, datetime.min.time())` lines in `seed_daily_data` change → `datetime.combine(day, shift.start_time)`. Nothing else.
- `shift = shifts[0]` (the seeded "Day" shift); `shift.start_time` is a `datetime.time(6, 0)` object (factory does `time.fromisoformat`) — no coercion needed.
- Deterministic (no new randomness), prod-safe (INSERT-only, no schema/DDL, allowlist unchanged). Existing `test_seed_sample_client.py` guards (dates via `func.date`, counts, determinism, FK-order, prod-safety static scan) stay green.
- Test fixture: `FIXED_ANCHOR = date(2026, 6, 15)`; tests call `_seed_admin(db_session)` then `seed.seed_client(db_session, spec, days=N, anchor=FIXED_ANCHOR)` (per the sibling tests in that file).

---

### Task 1: Seed entries at the shift start time + regression test

**Files:**
- Modify: `backend/scripts/_seed_operations.py` (two `day_dt` lines in `seed_daily_data`: the per-WO production/quality/downtime loop ~line 340, and the attendance loop ~line 455)
- Test: `backend/tests/test_scripts/test_seed_sample_client.py` (add one test)

**Interfaces:** none produced; `seed_daily_data` signature unchanged.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_scripts/test_seed_sample_client.py`:

```python
def test_seeded_entries_use_shift_start_time_not_midnight(db_session):
    """Operational entries are timestamped at their shift's start time (06:00 for
    the Day shift), not midnight — realistic data + lets the date-range boundary
    fix (#145) be exercised on live seed data."""
    from datetime import time
    from backend.orm import ProductionEntry, AttendanceEntry

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10, anchor=FIXED_ANCHOR)

    pe = db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").first()
    ae = db_session.query(AttendanceEntry).filter_by(client_id="DEMO-PIECE").first()
    assert pe is not None and ae is not None
    # Day shift starts 06:00; entries must carry that intraday time, not 00:00.
    assert pe.shift_date.time() == time(6, 0), f"production shift_date {pe.shift_date} not at shift start"
    assert ae.shift_date.time() == time(6, 0), f"attendance shift_date {ae.shift_date} not at shift start"
    assert pe.shift_date.time() != time(0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_seeded_entries_use_shift_start_time_not_midnight -v`
Expected: FAIL — current seed uses midnight, so `pe.shift_date.time() == time(0, 0)` → `assert time(0,0) == time(6,0)` fails.

- [ ] **Step 3: Apply the fix** — in `backend/scripts/_seed_operations.py` `seed_daily_data`, both occurrences of:

```python
day_dt = datetime.combine(day, datetime.min.time())
```
become:
```python
day_dt = datetime.combine(day, shift.start_time)
```

(There are exactly two: the per-work-order daily loop and the attendance loop. Confirm with `grep -n "datetime.combine(day, datetime.min.time())" backend/scripts/_seed_operations.py` before and after — after should return nothing. `shift` is already bound as `shifts[0]` in `seed_daily_data`; `datetime` and the ORM are already imported.)

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py -v`
Expected: PASS — the new test plus every existing seeder guard (determinism, idempotency, RESET_TABLE_ORDER, FK-enforcement, daily-data credibility). If any existing test fails asserting a midnight `shift_date`, that is a real coupling to fix in the same task — but none is expected (they group by `func.date`).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_operations.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "fix(seed): timestamp entries at shift start time, not midnight"
```

---

## Post-deploy: `--reset` re-seed + live boundary demo (the payoff)
After merge + VM deploy, re-seed the DEMO clients (idempotent seeder needs `--reset` to replace the midnight-dated data):
`docker compose -f docker-compose.prod.yml exec backend python -m backend.scripts.seed_sample_client --reset --days 90 --anchor <today>`.
Then the live boundary demo needs no probe row: a plain single-day API query (`/api/quality/kpi/defects-by-type?start_date=D&end_date=D` for a day D with data) returns rows whose entries are at 06:00 — which the pre-#145 code would have dropped. Confirm non-empty on the VM MariaDB.

## Self-Review
**Spec coverage:** both `day_dt` sites → Task 1 Step 3; non-midnight assertion → Task 1 Step 1; determinism/prod-safety preserved (no logic beyond the two lines) → Global Constraints; `--reset` re-seed + live demo → post-deploy. **Placeholders:** none — exact before/after and complete test code. **Consistency:** `shift.start_time` (a `time(6,0)`) used consistently; `time(6, 0)` in the test matches the seeded Day shift.

## Global verification
`cd backend && pytest tests/test_scripts/test_seed_sample_client.py -v`
